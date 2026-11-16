# Autonomy policy

Default deny: grants must be enabled, unexpired and contain the requested action. Owner/staff access is enforced at the transport boundary. Agent endpoints require owner access. Business capabilities are a separate gate, not permissions. Profile updates cannot change grants. Policy versions increment on every change and are recorded with tool results.

Local agent actions require explicit grants for profile updates, product creation/reads, caption drafts, expense capture/reads and supplied-aggregate calculation. Policy and capabilities are rechecked after model planning and before local execution. Switching off automation during planning blocks its action. Local effect/result/message/audit commit in one transaction.

Refunds and deletion require approval, which is not yet executable. Publishing and sync remain blocked until approved schedule/channel rules exist. No agent tool can make payments, change security, issue refunds, execute SQL or grant itself access. Existing external task calls already running may complete after revocation; provider cancellation is a future contract.

Abandoned planning runs can be cancelled by the owner. A late model response cannot execute cancelled work. Completed effects cannot be reversed through cancellation. New intent needs a new idempotency key; retries of the same message return its existing result.
