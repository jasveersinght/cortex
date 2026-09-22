from hands.compliance_words import is_clean, violations


def test_flags_english_claims():
    assert violations("100% covered, guaranteed payout")
    assert not is_clean("#RiskFree")


def test_flags_other_languages():
    assert not is_clean("dijamin dibayar")      # Malay / Indonesian
    assert not is_clean("รับประกันการจ่าย")      # Thai
    assert not is_clean("百分百理赔")             # Chinese


def test_clean_hashtags_pass():
    assert is_clean("#JewelleryInsurance #Singapore #InsurTech")
