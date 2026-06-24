import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, getdate, add_days, nowdate
from agrolocale.utils import ensure_item


class EstatePriceBand(Document):
    pass
