"""Names, actions and expected results shared by tests and the developer page."""
SCENARIOS={
    'normal':("Valid authorization completes delivery","Approve the current version, then check and commit.","Both checks pass and one delivery is created."),
    'no_grant':("No execution authorization","Attempt execution without authorization.","Wait for authorization; create no delivery."),
    'alternative':("Use another valid authorization","Provide two authorizations, then revoke one.","Reevaluate and complete with the remaining valid authorization."),
    'revoked':("Authorization revoked after checks","Check content, then revoke authorization before committing.","Recheck before commit detects invalid authorization and waits."),
    'expired':("Authorization expires after checks","Check content, advance to expiry, then commit.","Authorization is invalid at expiry; delivery is rejected."),
    'bad_scope':("Authorization belongs to another project","Provide authorization for a different project, then execute.","Another project's authorization cannot permit execution."),
    'bad_role':("Actor has view access only","Change the actor to viewer, then execute.","Execution is rejected even with authorization."),
    'edit_after_prepare':("Content changed after checks","Change the text after checks, then attempt commit.","Old results cannot authorize a new version."),
    'cancel':("Delivery cancelled after checks","Cancel after checks, then attempt commit.","Keep the cancelled state and create no delivery."),
    'retry':("Retry after authorization is restored","Execute after revocation, then add valid authorization and retry.","The first attempt waits; the second completes."),
    'duplicate':("Duplicate submission for one version","Execute and commit again after delivery.","The version still has exactly one delivery."),
    'worker_failure':("Check function raises an error","Make the check function raise an error.","Record the failed check and reject delivery."),
    'concurrent':("Concurrent submissions for one version","After checks, submit concurrently from four threads.","Create exactly one delivery."),
    'privacy':("Content contains a sensitive marker","Approve and execute synthetic text containing SECRET:.","Marker detection fails; reject delivery."),
    'resource_wait':("One slot runs two checks in sequence","Provide one slot and let the checksum check acquire it first.","The other check waits, resumes after release, and both must pass."),
    'parallel':("Two slots run two checks concurrently","Provide two slots and synchronize the running checks.","Both are observable as running; delivery waits for both."),
}
