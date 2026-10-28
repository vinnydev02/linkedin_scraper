from automation.scraper.extractor import PostExtractor


def test_extracts_urns_and_deduplicates_ids() -> None:
    text = (
        "urn:li:activity:123456789012345678 and "
        "urn:li:ugcPost:223456789012345678 and "
        "urn:li:activity:123456789012345678"
    )

    actual = PostExtractor().extract_urns_from_text(text)

    assert [(item.type, item.id) for item in actual] == [
        ("activity", "123456789012345678"),
        ("ugcPost", "223456789012345678"),
    ]


def test_extracts_activity_slug() -> None:
    actual = PostExtractor().extract_urns_from_text("/feed/update/activity-123456789012345678/")

    assert len(actual) == 1
    assert actual[0].type == "activity"
    assert actual[0].id == "123456789012345678"


def test_builds_post_url() -> None:
    from automation.models.post import PostReference

    record = PostExtractor().to_record(
        PostReference(type="share", id="123456789012345678"),
        "https://www.linkedin.com/",
    )

    assert record.post_url == (
        "https://www.linkedin.com/feed/update/urn:li:share:123456789012345678/"
    )
