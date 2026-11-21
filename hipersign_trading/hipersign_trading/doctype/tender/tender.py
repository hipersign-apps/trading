# Copyright (c) 2026, Hipersign
# v1.9.0 Construction (India): the rules are in hipersign_trading.api.construction
from frappe.model.document import Document


class Tender(Document):
	def validate(self):
		from hipersign_trading.api import construction as CN

		CN.validate_doc(self)
