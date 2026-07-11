from prometheus_client import Counter

auth_success_total = Counter("scep_authentication_success_total", "Successful authentications")
auth_failed_total = Counter("scep_authentication_failed_total", "Failed authentications")
auth_inactive_total = Counter(
    "scep_authentication_inactive_account_total", "Inactive-account authentication attempts"
)
account_created_total = Counter("scep_account_created_total", "Accounts created")
authorization_denied_total = Counter("scep_authorization_denied_total", "Authorization denials")
