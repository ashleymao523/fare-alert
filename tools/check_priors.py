# -*- coding: utf-8 -*-
import io, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(ROOT))
from core.sched_board import build_route_priors, load_sched_db, prior_minutes_for
from core.flights import estimate_arrival_time
IATA = {'重庆': 'CKG', '成都': 'CTU', '郑州': 'CGO', '曼谷': 'BKK'}
db = load_sched_db(str(ROOT / 'data'))
priors = build_route_priors(db)
print('priors cities:', len(priors))
for city, code in IATA.items():
    mins = prior_minutes_for(priors, city)
    if not mins:
        print(city, 'NO PRIOR')
        continue
    p = {'minutes': mins, 'n': 0}
    gc = estimate_arrival_time('08:00', 'HGH', code)
    pr = estimate_arrival_time('08:00', 'HGH', '', prior_minutes=p['minutes'])
    print(city, 'prior_min=', p['minutes'], 'n=', p['n'], 'arr_prior=', pr, 'arr_gc=', gc)
