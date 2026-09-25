import hashlib
import secrets
from dataclasses import dataclass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.config import Settings

@dataclass(frozen=True)
class CustomerScope:
    service_contract_sfid: str
    account_sfid: str

class FakeSalesforceAdapter:
    def __init__(self, records=None): self.records = records or [{"bp":"BP-1","ca":"CA-1","mobile":"+15555550100","email":"customer@example.com","service_contract_sfid":"SC-1","account_sfid":"AC-1"}]
    async def validate(self, bp, ca, mobile, email):
        for row in self.records:
            if (row["bp"],row["ca"],row["mobile"],row["email"].lower()) == (bp,ca,mobile,email.lower()):
                return CustomerScope(row["service_contract_sfid"], row["account_sfid"])
        return None

class MirrorSalesforceAdapter:
    """Read-only mirror lookup; identifiers originate only in validated settings."""
    def __init__(self, session: AsyncSession, settings: Settings): self.session, self.s = session, settings
    async def validate(self, bp, ca, mobile, email):
        s=self.s
        # Configuration names are deployment-controlled identifiers; values remain bound parameters.
        query = text(f"SELECT service_contract_sfid, account_sfid FROM {s.salesforce_contract_table} WHERE {s.salesforce_bp_field}=:bp AND {s.salesforce_ca_field}=:ca AND {s.salesforce_mobile_field}=:mobile AND {s.salesforce_email_field}=:email")
        row=(await self.session.execute(query,{"bp":bp,"ca":ca,"mobile":mobile,"email":email})).mappings().first()
        return CustomerScope(row["service_contract_sfid"],row["account_sfid"]) if row else None

class FakeOtpAdapter:
    def __init__(self): self.codes={}; self.fail=False
    async def send(self, destination_hash: str) -> str:
        if self.fail: raise RuntimeError("provider unavailable")
        ref=secrets.token_urlsafe(12); self.codes[ref]="123456"; return ref
    async def verify(self, reference: str, code: str) -> bool:
        return secrets.compare_digest(self.codes.get(reference,""), code)

def destination_digest(mobile: str) -> str: return hashlib.sha256(mobile.encode()).hexdigest()
