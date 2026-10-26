#pragma once
struct Document { int owner_id; int tenant_id; };
inline bool can_read(bool authenticated, int user_id, int tenant_id, Document doc) {
    return authenticated && tenant_id == doc.tenant_id && user_id == doc.owner_id;
}
