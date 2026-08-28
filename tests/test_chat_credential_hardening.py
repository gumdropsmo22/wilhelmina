from __future__ import annotations

import pytest

from services import chat_response


@pytest.mark.parametrize(
    "secret",
    [
        "password is hunter 2",
        "password is correct horse battery staple",
        "Alice's password is blue meadow silver lantern",
        "my password is correct horse battery staple",
        "my password is sunshine",
        "our passphrase is purplemonkey",
        "Alice's password is banana",
        "passphrase: correct horse battery staple",
        "routing number: 021000021",
        "routing number is 0210 0002 1",
        "bank account number: 1234567890",
        "IBAN: GB82 WEST 1234 5698 7654 32",
        "CVV: 123",
        "CVC is 9876",
        "card security code = 456",
    ],
)
def test_labelled_multitoken_and_banking_credentials_fail_closed(secret):
    with pytest.raises(chat_response.ChatInputRejected):
        chat_response.validate_chat_input(secret)
    with pytest.raises(chat_response.ChatInputRejected):
        chat_response.validate_chat_output(secret)


@pytest.mark.parametrize(
    "ordinary",
    [
        "Password managers are useful.",
        "A password is important for account security.",
        "A password is useful when an account matters.",
        "My password is forgotten, so I need to reset it.",
        "Her password is stored in a password manager.",
        "I forgot whether the bank calls it a routing number or sort code.",
        "What does CVV mean on a payment card?",
        "I need to renew my passport next year.",
    ],
)
def test_credential_topic_discussion_remains_allowed(ordinary):
    assert chat_response.validate_chat_input(ordinary) == ordinary
    assert chat_response.validate_chat_output(ordinary) == ordinary
