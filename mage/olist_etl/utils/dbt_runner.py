"""Bước dbt của pipeline Mage (BS-34): staging vừa nạp xong -> dbt build -> dds.

Dùng chung cho 2 pipeline (block dbt_build_full của full_load, dbt_build của incremental_load):
    0. run_id phải còn RUNNING - block nhận output cũ thì dừng        (etl_log.ensure_running)
    1. dbt build [--full-refresh]: seed -> model -> test theo đúng thứ tự phụ thuộc,
       log của dbt in ra Mage từng dòng ngay khi có
    2. đọc dbt/target/run_results.json -> etl_log.dbt_result (1 dòng / 1 seed, model, test)
    3. dbt báo lỗi (model lỗi, test FAIL, không kết nối được...) -> pipeline_run FAILED rồi báo lỗi cho Mage:
       block sau (set_lset / finish_full_run) không chạy nên LSET không tiến

Gọi dbt bằng tiến trình con - đúng lệnh `dbt build` vẫn gõ tay, vì dbt nằm sẵn trong container Mage.
Không dùng block dbt có sẵn của Mage: block đó không ghi được etl_log và không đánh dấu FAILED khi lỗi.

Staging đã COMMIT ở bước trước nên KHÔNG bị hoàn tác khi dbt lỗi. Incremental: lần chạy sau nạp lại
đúng batch đó (MERGE ra 0 INSERT / 0 UPDATE) rồi chạy dbt lại. Full Load: phải chạy lại full_load -
etl_log.check_staging_in_sync chặn Incremental cho tới lúc đó.
"""
import json
import os
import subprocess
import time
from collections import deque

import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.db import connect

# compose.yaml đặt 2 biến này cho container Mage - cùng project / profile với lệnh dbt gõ tay
DBT_PROJECT_DIR = os.getenv('DBT_PROJECT_DIR', '/home/src/dbt')
DBT_PROFILES_DIR = os.getenv('DBT_PROFILES_DIR', DBT_PROJECT_DIR)
RUN_RESULTS_PATH = os.path.join(DBT_PROJECT_DIR, 'target', 'run_results.json')

LOG_TAIL_LINES = 20     # số dòng log cuối giữ lại để báo lỗi khi dbt dừng trước khi chạy được node nào
MAX_FAILED_NODES = 3    # số node lỗi kể tên trong pipeline_run.error_message


class DbtBuildFailed(Exception):
    """dbt build kết thúc với mã thoát khác 0 (có node lỗi / test FAIL, hoặc dbt không chạy được)."""


def run_dbt_build(run_id, full_refresh=False):
    """Chạy dbt build cho lần chạy run_id. Trả về DataFrame kết quả từng node (etl_log.dbt_result).

    full_refresh: Full Load làm lại staging từ đầu -> dựng lại cả model incremental (dim_customer, dim_geography).
    Lỗi: ghi FAILED cho lần chạy rồi báo lỗi lại cho Mage (block hiện màu đỏ).
    run_id không còn RUNNING (chạy riêng block với output cũ): báo StaleRunError, không chạy dbt, không ghi gì.
    """
    log_conn = connect(autocommit=True)
    try:
        etl_log.ensure_running(log_conn, run_id)
        try:
            command = ['dbt', 'build', '--project-dir', DBT_PROJECT_DIR, '--profiles-dir', DBT_PROFILES_DIR]
            if full_refresh:
                command.append('--full-refresh')
            _remove_old_run_results()
            print('Chạy: ' + ' '.join(command), flush=True)
            started = time.monotonic()
            exit_code, log_tail = _run(command)
            seconds = time.monotonic() - started

            results = _read_run_results()
            if results is not None:
                etl_log.add_dbt_results(log_conn, run_id, [_result_row(r) for r in results])
            counts = _count(results)
            print(f'dbt build xong sau {seconds:.1f} giây, mã thoát {exit_code}: {counts}')

            if exit_code != 0:
                raise DbtBuildFailed(_error_message(exit_code, counts, results, log_tail))
            if results is None:
                print('Cảnh báo: không đọc được run_results.json -> không ghi etl_log.dbt_result')
        except Exception as exc:
            message = str(exc) if isinstance(exc, DbtBuildFailed) else etl_log.short_error(exc)
            etl_log.fail_run(log_conn, run_id, message)
            print(f'LỖI ở bước dbt - ghi FAILED cho run_id {run_id}, LSET không tiến: {message}')
            raise

        summary = etl_log.dbt_summary(log_conn, run_id)
        # block sau cần run_id kể cả khi không đọc được kết quả từng node
        return summary if not summary.empty else pd.DataFrame([{'run_id': run_id}])
    finally:
        log_conn.close()


def _remove_old_run_results():
    """Xóa run_results.json của lần dbt trước: dbt dừng sớm thì không ghi file mới -> không đọc nhầm file cũ."""
    try:
        os.remove(RUN_RESULTS_PATH)
    except FileNotFoundError:
        pass


def _run(command):
    """Chạy dbt, in từng dòng log ra Mage ngay khi có. Trả về (mã thoát, các dòng log cuối)."""
    env = dict(os.environ, DBT_USE_COLORS='false')   # bỏ mã màu: log trong Mage hiện thành ký tự lạ
    tail = deque(maxlen=LOG_TAIL_LINES)
    with subprocess.Popen(command, cwd=DBT_PROJECT_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace') as proc:
        for line in proc.stdout:
            line = line.rstrip()
            print(line, flush=True)
            if line:
                tail.append(line)
    return proc.returncode, list(tail)


def _read_run_results():
    """Kết quả từng node của lần dbt vừa chạy; None nếu dbt không ghi file (dừng trước khi chạy được node nào)."""
    try:
        with open(RUN_RESULTS_PATH, encoding='utf-8') as f:
            return json.load(f)['results']
    except FileNotFoundError:
        return None


def _result_row(result):
    """1 phần tử của run_results.json -> 1 dòng etl_log.dbt_result."""
    parts = result['unique_id'].split('.')   # model.olist_dw.fact_sales · test.olist_dw.<tên test>.<mã hash>
    resource_type = parts[0]
    timing = result.get('timing') or []      # [compile, execute]; node bị bỏ qua: []
    rows = (result.get('adapter_response') or {}).get('rows_affected')
    return {
        'unique_id': result['unique_id'],
        'resource_type': resource_type,
        'node_name': parts[2] if len(parts) > 2 else result['unique_id'],
        'relation_name': _short_relation(result.get('relation_name')),
        'status': result['status'],
        'rows_affected': rows if resource_type != 'test' and rows is not None and rows >= 0 else None,
        'failures': result.get('failures') if resource_type == 'test' else None,
        'execution_time': result.get('execution_time'),
        'started_at': timing[0]['started_at'] if timing else None,
        'finished_at': timing[-1]['completed_at'] if timing else None,
        'message': result.get('message'),
    }


def _short_relation(relation):
    """'"olist_dw"."dds"."fact_sales"' -> 'dds.fact_sales' (bỏ tên database cho dễ đọc)."""
    if not relation:
        return None
    return '.'.join(part.strip('"') for part in relation.split('.')[-2:])


def _count(results):
    """Đếm giống dòng 'Done. PASS=... WARN=... ERROR=... SKIP=... TOTAL=...' cuối log dbt (test FAIL tính vào ERROR)."""
    if results is None:
        return 'không có kết quả từng node'
    statuses = [r['status'] for r in results]
    passed = sum(s in ('success', 'pass') for s in statuses)
    errors = sum(s in ('error', 'fail') for s in statuses)
    return (f"PASS={passed} WARN={statuses.count('warn')} ERROR={errors} "
            f"SKIP={statuses.count('skipped')} TOTAL={len(statuses)}")


def _error_message(exit_code, counts, results, log_tail):
    """Thông báo ngắn cho pipeline_run.error_message: số node theo trạng thái + vài node lỗi đầu tiên."""
    if results is None:
        # dbt dừng trước khi chạy được node nào: thiếu profiles.yml / package, sai kết nối, lỗi biên dịch...
        detail = ' | '.join(log_tail[-5:])
        return f'dbt build không chạy được (mã thoát {exit_code}): {detail}'[:etl_log.MAX_ERROR_LENGTH]

    failed = [_result_row(r) for r in results if r['status'] in ('error', 'fail')]
    notes = []
    for row in failed[:MAX_FAILED_NODES]:
        note = f"{row['resource_type']} {row['node_name']}: {row['status']}"
        if row['failures']:
            note += f" {row['failures']} dòng vi phạm (xem bảng {row['relation_name']})"
        elif row['message']:
            note += ' - ' + ' '.join(str(row['message']).split())[:200]
        notes.append(note)
    if len(failed) > MAX_FAILED_NODES:
        notes.append(f'... và {len(failed) - MAX_FAILED_NODES} node lỗi khác')
    if not notes:   # mã thoát khác 0 mà không node nào lỗi: lấy log cuối
        notes.append(' | '.join(log_tail[-3:]))
    return f"dbt build lỗi (mã thoát {exit_code}): {counts}. {'; '.join(notes)}"[:etl_log.MAX_ERROR_LENGTH]
