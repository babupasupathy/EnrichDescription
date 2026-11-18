from enrich.compliance import check_listing, copied_phrases


def rules(issues):
    return {i.rule for i in issues}


def test_clean_listing_passes():
    issues = check_listing("ebay", "Floral Wrap Midi Dress Women Rayon Flutter Sleeve Size M",
                           [], "A breezy midi dress.", ["Something else entirely"])
    assert issues == []


def test_ebay_title_over_80_chars_fails():
    issues = check_listing("ebay", "x" * 81, [], "d", [])
    assert "ebay: title max 80 chars" in rules(issues)


def test_word_repeated_three_times_fails():
    issues = check_listing("amazon", "Dress dress DRESS for women", [], "d", [])
    assert "No word more than twice in a title" in rules(issues)


def test_special_characters_fail():
    issues = check_listing("amazon", "Best dress ever!", [], "d", [])
    assert "No special characters in titles" in rules(issues)


def test_amazon_more_than_five_bullets_fails():
    issues = check_listing("amazon", "Dress", ["b"] * 6, "d", [])
    assert "amazon: at most 5 bullets" in rules(issues)


def test_copy_check_catches_eight_identical_words_ignoring_case_and_punctuation():
    source = "Made from soft, breathable rayon fabric that keeps you cool all summer long."
    ours = "Crafted with Soft Breathable Rayon fabric that keeps you cool all day."
    # The shared run is 9 words long, so it contains two 8-word phrases.
    assert sorted(copied_phrases(ours, [source])) == [
        "breathable rayon fabric that keeps you cool all",
        "soft breathable rayon fabric that keeps you cool",
    ]


def test_copy_check_allows_short_shared_keywords():
    source = "Women's summer maxi dress for iPhone 16 Pro lovers"
    ours = "Women's summer maxi dress with pockets"
    assert copied_phrases(ours, [source]) == []
