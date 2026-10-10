# Power BI – Semantic Model & Dashboard

## Semantic Model

### Relationships
| Từ (Fact) | Đến (Dimension) | Cardinality | Hướng lọc |
|-----------|-----------------|-------------|-----------|
|           |                 | *:1         | Single    |

### Hierarchies
| Dimension | Hierarchy |
|-----------|-----------|
| `dim_date` | Năm → Quý → Tháng → Ngày |
|           |           |

### Measures (DAX)
> Toàn bộ DAX được sao lưu trong `measures.dax`.

| Measure | Mô tả | Dùng ở trang |
|---------|-------|--------------|
|         |       |              |

## Dashboard

### Trang 1 – Overview (Descriptive)
- **KPI cards:**
- **Biểu đồ xu hướng:**
- **Biểu đồ phân bố:**
- **Slicers / Filters:**
- **Điểm bất thường cần chú ý:**

### Trang 2 – Detailed / Diagnostic
- **Drill-down / Drill-through:**
- **Phân tích yếu tố đóng góp:**
- **Bằng chứng định lượng:**

## Ảnh chụp
![Overview](../docs/images/dashboard_overview.png)
![Diagnostic](../docs/images/dashboard_diagnostic.png)
