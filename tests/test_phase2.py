from app.amazon import parse_csv
from app.analytics import analyze_regions, analyze_series, opportunity_rows
from app.storage import Storage


def points(values, keyword="coffee"):
    return [
        {
            "date": f"2026-01-{i + 1:02d}",
            "values": {keyword: value},
            "is_partial": False,
        }
        for i, value in enumerate(values)
    ]


def test_trend_classifications_are_explainable():
    sustained = analyze_series(
        points([20, 22, 24, 26, 28, 30, 32, 34, 36, 38]), "coffee"
    )
    noisy = analyze_series(points([5, 95, 7, 92, 6, 90, 8, 50, 30, 20]), "coffee")
    insufficient = analyze_series(points([1, 2, 3]), "coffee")
    assert sustained["classification"] == "持续趋势"
    assert noisy["classification"] == "噪音"
    assert insufficient["classification"] == "数据不足"
    assert sustained["evidence"]


def test_region_concentration():
    result = analyze_regions(
        [
            {"name": "A", "values": {"coffee": 100}},
            {"name": "B", "values": {"coffee": 10}},
            {"name": "C", "values": {"coffee": 5}},
        ],
        "coffee",
    )
    assert result["classification"] == "局部集中"
    assert result["top_share"] > 0.8


def test_amazon_csv_supports_bom_chinese_columns_and_warns():
    rows, warnings = parse_csv(
        "\ufeff关键词,搜索量,排名\ncoffee beans,1,20\nmatcha,abc,5\n".encode()
    )
    assert rows[0]["keyword"] == "coffee beans"
    assert rows[0]["search_volume"] == 1
    assert rows[1]["search_volume"] is None
    assert warnings


def test_opportunities_are_sorted_and_match_long_tail():
    result = {
        "request": {"keywords": ["coffee"]},
        "series": points([20, 22, 24, 26, 28, 30, 32, 34, 36, 40]),
    }
    rows = opportunity_rows(
        result,
        [{"keyword": "coffee beans", "rank": 80}, {"keyword": "unrelated", "rank": 1}],
    )
    assert len(rows) == 1
    assert rows[0]["keyword"] == "coffee beans"
    assert rows[0]["opportunity_score"] >= 0


def test_storage_schedule_rejects_other_intervals(tmp_path):
    storage = Storage(tmp_path / "trendscope.db")
    try:
        storage.add_schedule(
            {
                "keywords": ["coffee"],
                "geo": "US",
                "timeframe": "today 12-m",
                "gprop": "",
            },
            3,
        )
    except ValueError as exc:  # pragma: no cover
        raise AssertionError(exc)
    assert storage.schedules()[0]["interval_days"] == 3
