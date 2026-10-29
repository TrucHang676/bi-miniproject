"""Tạo tình huống lỗi trên file batch để demo pipeline Mage (docs/pipeline_rules.md B8, B10), rồi trả file về gốc.

Chỉ sửa file trong data/batches/ (sinh lại được bằng split_batches.py), không đụng database.
Mọi file bị sửa được sao lưu vào data/batches/_demo_backup/ trước, lệnh `restore` chép lại y nguyên.

Chạy trong container Mage (giống split_batches.py), ở thư mục gốc repo:
    docker compose exec mage python scripts/demo_faults.py status
    docker compose exec mage python scripts/demo_faults.py missing-column 2018-02
    docker compose exec mage python scripts/demo_faults.py bad-rows 2018-02
    docker compose exec mage python scripts/demo_faults.py delete-order 2018-03
    docker compose exec mage python scripts/demo_faults.py missing-file 2018-02
    docker compose exec mage python scripts/demo_faults.py restore

Tình huống                    Pipeline sẽ thấy gì
  missing-column <batch>      order_payments.csv mất tên cột payment_type ở dòng tiêu đề
                              -> columns_match FAIL, cả batch dừng, lần chạy FAILED, staging hoàn tác
  missing-file <batch>        order_payments.csv bị đổi tên thành .csv.hidden
                              -> file_exists FAIL, cả batch dừng, lần chạy FAILED
  bad-rows <batch>            order_payments.csv: 1 dòng trống order_id, 1 dòng bị lặp, 1 dòng payment_value = 'abc'
                              -> not_null_key / duplicate_key / type_cast WARN, 4 dòng vào dq.rejected_rows,
                                 các dòng còn lại vẫn nạp, lần chạy SUCCESS
  delete-order <batch>        thêm deleted_orders.csv: 1 đơn có thật của batch FULL + 1 mã đơn không tồn tại
                              -> đơn có thật bị xóa mềm (rows_deleted = 1), dòng còn lại key_exists WARN
"""
import csv
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DIR = os.getenv('OLIST_BATCH_DIR', os.path.join(ROOT, 'data', 'batches'))
BACKUP_DIR = os.path.join(BATCH_DIR, '_demo_backup')
CREATED_LIST = os.path.join(BACKUP_DIR, 'created_files.txt')
TABLE = 'order_payments'


def batch_path(batch_id, name):
    path = os.path.join(BATCH_DIR, batch_id, name)
    if not os.path.isdir(os.path.dirname(path)):
        sys.exit(f'Không có thư mục batch {batch_id} trong {BATCH_DIR}')
    return path


def backup(batch_id, name):
    """Sao lưu file gốc 1 lần duy nhất (lần sửa sau không đè bản gốc)."""
    src = batch_path(batch_id, name)
    dst = os.path.join(BACKUP_DIR, batch_id, name)
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def remember_created(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(CREATED_LIST, 'a', encoding='utf-8') as f:
        f.write(os.path.relpath(path, BATCH_DIR) + '\n')


def read_rows(path):
    with open(path, encoding='utf-8', newline='') as f:
        return list(csv.reader(f))


def write_rows(path, rows):
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(buf.getvalue())


def missing_column(batch_id):
    path = batch_path(batch_id, f'{TABLE}.csv')
    backup(batch_id, f'{TABLE}.csv')
    with open(path, encoding='utf-8', newline='') as f:
        header, rest = f.read().split('\n', 1)
    if 'payment_type,' not in header:
        sys.exit('Tiêu đề đã không còn cột payment_type (đã chạy lệnh này rồi?)')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(header.replace('payment_type,', '', 1) + '\n' + rest)
    print(f'{batch_id}/{TABLE}.csv: đã xóa tên cột payment_type ở dòng tiêu đề (dữ liệu giữ nguyên)')
    print('  tiêu đề mới: ' + header.replace('payment_type,', '', 1))


def missing_file(batch_id):
    path = batch_path(batch_id, f'{TABLE}.csv')
    if not os.path.exists(path):
        sys.exit(f'{batch_id}/{TABLE}.csv đã không còn (đã chạy lệnh này rồi?)')
    backup(batch_id, f'{TABLE}.csv')
    os.rename(path, path + '.hidden')
    remember_created(path + '.hidden')
    print(f'{batch_id}/{TABLE}.csv: đã đổi tên thành {TABLE}.csv.hidden -> batch thiếu 1 file')


def bad_rows(batch_id):
    path = batch_path(batch_id, f'{TABLE}.csv')
    backup(batch_id, f'{TABLE}.csv')
    rows = read_rows(path)
    header, data = rows[0], rows[1:]
    if 'payment_type' not in header:
        sys.exit('Tiêu đề file đang bị sửa (missing-column): chạy restore trước rồi mới tạo dòng hỏng')
    if len(data) < 3:
        sys.exit(f'{batch_id}/{TABLE}.csv có ít hơn 3 dòng, chọn batch khác')
    col = {name: i for i, name in enumerate(header)}
    data[0][col['order_id']] = ''              # bản ghi 1: trống khóa       -> not_null_key
    data[2][col['payment_value']] = 'abc'      # bản ghi 3: sai kiểu số      -> type_cast
    data.append(list(data[1]))                 # bản ghi 2 lặp ở cuối file   -> duplicate_key (loại cả 2 dòng)
    write_rows(path, [header] + data)
    print(f'{batch_id}/{TABLE}.csv: đã tạo 3 kiểu dòng hỏng')
    print('  bản ghi 1           : order_id để trống          -> not_null_key  (1 dòng)')
    print(f'  bản ghi 2 + {len(data):<8}: lặp khóa {data[1][col["order_id"]]}, {data[1][col["payment_sequential"]]} -> duplicate_key (2 dòng)')
    print('  bản ghi 3           : payment_value = abc         -> type_cast     (1 dòng)')


def delete_order(batch_id):
    if batch_id == 'FULL':
        sys.exit('Batch FULL không xét file xóa đơn, chọn 1 batch Incremental (VD 2018-03)')
    path = batch_path(batch_id, 'deleted_orders.csv')
    if os.path.exists(path):
        sys.exit(f'{batch_id}/deleted_orders.csv đã có (đã chạy lệnh này rồi?)')
    order_id = read_rows(batch_path('FULL', 'orders.csv'))[1][0]   # đơn đầu tiên của batch FULL - chắc chắn đã có trong staging
    month = batch_id[:7]
    rows = [['order_id', 'deleted_at', 'batch_id'],
            [order_id, f'{month}-10 09:00:00', batch_id],
            ['khongtontai0000000000000000000000', f'{month}-12 09:00:00', batch_id]]
    write_rows(path, rows)
    remember_created(path)
    print(f'{batch_id}/deleted_orders.csv: đã tạo')
    for r in rows:
        print('  ' + ','.join(r))


def restore():
    if not os.path.isdir(BACKUP_DIR):
        print('Không có gì để trả lại: chưa tạo tình huống lỗi nào')
        return
    if os.path.exists(CREATED_LIST):
        with open(CREATED_LIST, encoding='utf-8') as f:
            for rel in filter(None, (line.strip() for line in f)):
                path = os.path.join(BATCH_DIR, rel)
                if os.path.exists(path):
                    os.remove(path)
                    print(f'Đã xóa {rel}')
    for dirpath, _, files in os.walk(BACKUP_DIR):
        for name in files:
            if name == 'created_files.txt':
                continue
            src = os.path.join(dirpath, name)
            rel = os.path.relpath(src, BACKUP_DIR)
            shutil.copy2(src, os.path.join(BATCH_DIR, rel))
            print(f'Đã trả về bản gốc {rel}')
    shutil.rmtree(BACKUP_DIR)
    print('Xong: file batch đã như lúc chạy split_batches.py')


def status():
    if not os.path.isdir(BACKUP_DIR):
        print('File batch đang nguyên gốc (chưa tạo tình huống lỗi nào)')
        return
    print('Đang có tình huống lỗi trên các file:')
    for dirpath, _, files in os.walk(BACKUP_DIR):
        for name in files:
            if name != 'created_files.txt':
                print('  sửa: ' + os.path.relpath(os.path.join(dirpath, name), BACKUP_DIR))
    if os.path.exists(CREATED_LIST):
        with open(CREATED_LIST, encoding='utf-8') as f:
            for rel in filter(None, (line.strip() for line in f)):
                print('  thêm: ' + rel)
    print('Trả về gốc: docker compose exec mage python scripts/demo_faults.py restore')


COMMANDS = {'missing-column': missing_column, 'missing-file': missing_file, 'bad-rows': bad_rows,
            'delete-order': delete_order}

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in ('restore', 'status'):
        {'restore': restore, 'status': status}[sys.argv[1]]()
    elif len(sys.argv) == 3 and sys.argv[1] in COMMANDS:
        COMMANDS[sys.argv[1]](sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
