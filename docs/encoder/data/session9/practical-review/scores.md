# Practical numerical screening

MAE is average component error on the 0–255 intensity scale. PM visual review remains pending.

| Case | GramPy raw MAE | Pi fldigi raw MAE | Pi aligned MAE | Functional / numerical screen |
| --- | ---: | ---: | ---: | --- |
| gray64-p8-card | 0.77 | 8.61 | 1.45 | PASS |
| gray64-p4-photo | 0.82 | 2.46 | 0.79 | PASS |
| gray64-p2-chart | 10.25 | 9.99 | 9.99 | PASS |
| rgb64-p8-photo | 0.36 | 0.60 | 0.60 | PASS |
| rgb64-p4-card | 2.63 | 3.08 | 3.08 | PASS |
| rgb64-p2-chart | 11.31 | 10.70 | 10.70 | PASS |
| gray32-p8-card | outside picture scope | 3.63 | 3.63 | PASS |
| gray32-p4-photo | outside picture scope | 1.63 | 1.63 | PASS |
| gray32-p2-chart | outside picture scope | 14.11 | 12.53 | PASS |
| mixed-broadcast-photo | 1.38 | 5.71 | 1.69 | PASS |
