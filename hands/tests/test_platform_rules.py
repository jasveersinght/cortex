from hands.config import get_settings
from hands.platform_rules import compose_final_text, count_length, rule_for


def rule(name):
    return rule_for(name, get_settings())


def test_x_counts_urls_as_23_and_cjk_as_2():
    x = rule("x")
    assert count_length("see https://example.com/a/very/long/path/that/goes/on", x) == 4 + 23
    assert count_length("保险", x) == 4          # each CJK char weighs 2 on X
    assert count_length("abc", x) == 3
    assert count_length("ทดสอบ", x) == 5        # Thai stays weight 1


def test_emoji_costs_two_units():
    assert count_length("🚀", rule("tiktok")) == 2
    assert count_length("🚀", rule("x")) == 2


def test_instagram_line_breaks_count_twice():
    ig = rule("instagram")
    assert count_length("a\nb", ig) == 4


def test_linkedin_url_counts_24():
    li = rule("linkedin")
    assert count_length("https://example.com/a-very-very-long-link-indeed", li) == 24


def test_compose_never_touches_body_and_respects_limit():
    x = rule("x")
    body = "a" * 270
    text, _, used = compose_final_text(body, ["#One", "#Two"], x)
    assert used == ["#One"] and count_length(text, x) <= 280      # second tag would overflow, so it is dropped
    body = "a" * 277
    text, comment, used = compose_final_text(body, ["#One", "#Two"], x)
    assert text == body and used == [] and comment is None       # nothing fits: hashtags dropped, body untouched


def test_compose_inline_and_first_comment():
    text, comment, used = compose_final_text("Hello", ["#A", "#B", "#C"], rule("linkedin"))
    assert text == "Hello\n\n#A #B #C" and comment is None and used == ["#A", "#B", "#C"]
    text, comment, used = compose_final_text("Hello", ["#A", "#B"], rule("instagram"))
    assert text == "Hello" and comment == "#A #B"


def test_max_hashtags_enforced():
    _, _, used = compose_final_text("Hi", ["#1a", "#2a", "#3a"], rule("x"))
    assert len(used) == 2
