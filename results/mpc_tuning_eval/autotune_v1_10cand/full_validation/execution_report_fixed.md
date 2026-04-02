# Full validation report (generated from summary_full_validation.json)

## Candidates checked
- cand_001
- cand_005
- cand_008

## Baseline sources
- rc: results\mpc_tuning_eval\baseline\rc
- pinn: results\mpc_tuning_eval\baseline\pinn
- rbc: results\mpc_tuning_eval\baseline\rbc

## Results by Controller/Episode
| Controller | Episode | baseline | candidate | delta % (candidate vs baseline) |
|---|---|---|---|---:|
| rc | te_ext_01 | cost=0.20896454608622972, tdis=0.0, solve_ms=2.515 | cost=0.20896459727012887, tdis=0.0, solve_ms=2.178 | cost 0.00%; solve_ms -0.34 ms |
| rc | te_ext_01 | cost=0.20896454608622972, tdis=0.0, solve_ms=2.515 | cost=0.20896453997391576, tdis=0.0, solve_ms=1.92 | cost -0.00%; solve_ms -0.60 ms |
| rc | te_ext_01 | cost=0.20896454608622972, tdis=0.0, solve_ms=2.515 | cost=0.2089645589458536, tdis=0.0, solve_ms=1.856 | cost 0.00%; solve_ms -0.66 ms |
| rc | te_ext_02 | cost=0.20904423471526667, tdis=0.0, solve_ms=2.888 | cost=0.20904429749391595, tdis=0.0, solve_ms=1.958 | cost 0.00%; solve_ms -0.93 ms |
| rc | te_ext_02 | cost=0.20904423471526667, tdis=0.0, solve_ms=2.888 | cost=0.20904424020805634, tdis=0.0, solve_ms=2.058 | cost 0.00%; solve_ms -0.83 ms |
| rc | te_ext_02 | cost=0.20904423471526667, tdis=0.0, solve_ms=2.888 | cost=0.20904425916087316, tdis=0.0, solve_ms=2.171 | cost 0.00%; solve_ms -0.72 ms |
| rc | te_std_01 | cost=0.13601818267125532, tdis=0.0, solve_ms=2.879 | cost=0.13605364788565538, tdis=0.0, solve_ms=2.079 | cost 0.03%; solve_ms -0.80 ms |
| rc | te_std_01 | cost=0.13601818267125532, tdis=0.0, solve_ms=2.879 | cost=0.13604276737499618, tdis=0.0, solve_ms=1.951 | cost 0.02%; solve_ms -0.93 ms |
| rc | te_std_01 | cost=0.13601818267125532, tdis=0.0, solve_ms=2.879 | cost=0.13602213936763505, tdis=0.0, solve_ms=2.078 | cost 0.00%; solve_ms -0.80 ms |
| rc | te_std_02 | cost=0.015767934059366773, tdis=0.0, solve_ms=4.288 | cost=0.1930934969383334, tdis=0.0, solve_ms=1.99 | cost 1124.60%; solve_ms -2.30 ms |
| rc | te_std_02 | cost=0.015767934059366773, tdis=0.0, solve_ms=4.288 | cost=0.193093498940072, tdis=0.0, solve_ms=1.924 | cost 1124.60%; solve_ms -2.36 ms |
| rc | te_std_02 | cost=0.015767934059366773, tdis=0.0, solve_ms=4.288 | cost=0.1930935746919043, tdis=0.0, solve_ms=1.962 | cost 1124.60%; solve_ms -2.33 ms |
| pinn | te_ext_01 | cost=0.1288476691100399, tdis=0.6904492873867961, solve_ms=127.568 | cost=0.13878199259285184, tdis=0.0, solve_ms=132.466 | cost 7.71%; tdis -100.00%; solve_ms 4.90 ms |
| pinn | te_ext_01 | cost=0.1288476691100399, tdis=0.6904492873867961, solve_ms=127.568 | cost=0.1385858411733986, tdis=0.0, solve_ms=131.019 | cost 7.56%; tdis -100.00%; solve_ms 3.45 ms |
| pinn | te_ext_01 | cost=0.1288476691100399, tdis=0.6904492873867961, solve_ms=127.568 | cost=0.1386315955922958, tdis=0.0, solve_ms=132.581 | cost 7.59%; tdis -100.00%; solve_ms 5.01 ms |
| pinn | te_ext_02 | cost=0.13832980058552194, tdis=0.07392060970451221, solve_ms=127.713 | cost=0.13885346471830448, tdis=0.0, solve_ms=130.249 | cost 0.38%; tdis -100.00%; solve_ms 2.54 ms |
| pinn | te_ext_02 | cost=0.13832980058552194, tdis=0.07392060970451221, solve_ms=127.713 | cost=0.13865729583600991, tdis=0.0, solve_ms=131.832 | cost 0.24%; tdis -100.00%; solve_ms 4.12 ms |
| pinn | te_ext_02 | cost=0.13832980058552194, tdis=0.07392060970451221, solve_ms=127.713 | cost=0.13870308845855142, tdis=0.0, solve_ms=133.694 | cost 0.27%; tdis -100.00%; solve_ms 5.98 ms |
| pinn | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=35.744 | cost=0.05819605300296641, tdis=0.0, solve_ms=93.66 | cost 20.35%; tdis -100.00%; solve_ms 57.92 ms |
| pinn | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=35.744 | cost=0.05783753914553928, tdis=0.0, solve_ms=102.64 | cost 19.60%; tdis -100.00%; solve_ms 66.90 ms |
| pinn | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=35.744 | cost=0.05784129542727816, tdis=0.0, solve_ms=128.589 | cost 19.61%; tdis -100.00%; solve_ms 92.84 ms |
| pinn | te_std_02 | cost=0.004149104364297357, tdis=0.0, solve_ms=434.202 | cost=0.13777891145664345, tdis=0.0, solve_ms=53.125 | cost 3220.69%; solve_ms -381.08 ms |
| pinn | te_std_02 | cost=0.004149104364297357, tdis=0.0, solve_ms=434.202 | cost=0.13772841036348052, tdis=0.0, solve_ms=54.389 | cost 3219.47%; solve_ms -379.81 ms |
| pinn | te_std_02 | cost=0.004149104364297357, tdis=0.0, solve_ms=434.202 | cost=0.13780824014560628, tdis=0.0, solve_ms=53.697 | cost 3221.40%; solve_ms -380.50 ms |
| rbc | te_ext_01 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_ext_01 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_ext_01 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12799340273899165, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_ext_02 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_ext_02 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_ext_02 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost=0.12806431027759613, tdis=0.9180230829800947, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_std_01 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost=0.04835749296774106, tdis=0.20702369425814215, solve_ms=0.0 | cost 0.00%; tdis 0.00%; solve_ms 0.00 ms |
| rbc | te_std_02 | cost=0.0014070631678779256, tdis=0.0, solve_ms=0.0 | cost=0.11312208248698438, tdis=1.3737305048752997, solve_ms=0.0 | cost 7939.59%; solve_ms 0.00 ms |
| rbc | te_std_02 | cost=0.0014070631678779256, tdis=0.0, solve_ms=0.0 | cost=0.11312208248698438, tdis=1.3737305048752997, solve_ms=0.0 | cost 7939.59%; solve_ms 0.00 ms |
| rbc | te_std_02 | cost=0.0014070631678779256, tdis=0.0, solve_ms=0.0 | cost=0.11312208248698438, tdis=1.3737305048752997, solve_ms=0.0 | cost 7939.59%; solve_ms 0.00 ms |

## Aggregates per candidate (from summary_full_validation.json)
| Candidate | Controller | cost_mean | tdis_mean | solve_mean_ms | wall_time_s_mean | smoothness_mean |
|---|---|---:|---:|---:|---:|---:|
| cand_001 | pinn | 0.11840260544269154 | 0.0 | 102.375 | 116.63 | 0.530075 |
| cand_001 | rbc | 0.1043843221178283 | 0.8542000912734078 | 0.0 | 28.3825 | 0.0 |
| cand_001 | rc | 0.1867890098970084 | 0.0 | 2.05125 | 37.135 | 3.0003 |
| cand_005 | pinn | 0.11820227162960707 | 0.0 | 104.97 | 117.475 | 0.532875 |
| cand_005 | rbc | 0.1043843221178283 | 0.8542000912734078 | 0.0 | 27.2575 | 0.0 |
| cand_005 | rc | 0.18678626162426007 | 0.0 | 1.96325 | 36.832499999999996 | 3.0003 |
| cand_008 | pinn | 0.11824605490593292 | 0.0 | 112.14025 | 123.6825 | 0.5267 |
| cand_008 | rbc | 0.1043843221178283 | 0.8542000912734078 | 0.0 | 28.9125 | 0.0 |
| cand_008 | rc | 0.18678113304156652 | 0.0 | 2.01675 | 40.19 | 3.0003 |