# -*- coding: utf-8 -*-
"""Data source registry: what is available / planned, shown in Web UI."""

SOURCE_REGISTRY = {
    "qunar-calendar": {
        "kind": "flight",
        "name": "去哪儿·价格日历",
        "status": "可用",
        "desc": "免登录免签名的公开接口,一次返回365天每日最低价+最低价航班号(挂牌价,不含券后)",
    },
    "ctrip-h5": {
        "kind": "flight",
        "name": "携程H5(规划中)",
        "status": "规划中",
        "desc": "备选交叉验证源,待接口侦查",
    },
    "airline-official": {
        "kind": "flight",
        "name": "航司官网聚合(规划中)",
        "status": "规划中",
        "desc": "西部/长龙/川航等官网直查,风控宽松,适合多源比价",
    },
    "12306-train": {
        "kind": "train",
        "name": "12306·票价查询",
        "status": "可用",
        "desc": "免登录低频查询,结果缓存24小时;学生票按公布价75折估算",
    },
}
