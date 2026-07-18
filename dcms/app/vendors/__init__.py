from app.models import VendorType
from app.vendors.base import BaseVendorAdapter
from app.vendors.cisco import CiscoAdapter
from app.vendors.fortinet import FortinetAdapter
from app.vendors.juniper import JuniperAdapter

_ADAPTERS: dict[VendorType, BaseVendorAdapter] = {
    VendorType.CISCO: CiscoAdapter(),
    VendorType.JUNIPER: JuniperAdapter(),
    VendorType.FORTINET: FortinetAdapter(),
}


def get_vendor_adapter(vendor: VendorType) -> BaseVendorAdapter:
    return _ADAPTERS.get(vendor, CiscoAdapter())
