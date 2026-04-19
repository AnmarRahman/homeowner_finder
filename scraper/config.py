from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class LAOpenDataConfig:
    dataset_url: str = os.getenv("LA_DATASET_URL", "").strip()
    page_size: int = int(os.getenv("LA_PAGE_SIZE", "100"))
    field_owner: str = os.getenv("LA_FIELD_OWNER", "owner_name")
    field_property_address: str = os.getenv("LA_FIELD_PROPERTY_ADDRESS", "property_address")
    field_mailing_address: str = os.getenv("LA_FIELD_MAILING_ADDRESS", "mailing_address")
    field_city: str = os.getenv("LA_FIELD_CITY", "city")
    field_state: str = os.getenv("LA_FIELD_STATE", "state")
    field_zip: str = os.getenv("LA_FIELD_ZIP", "zip")
    field_parcel_id: str = os.getenv("LA_FIELD_PARCEL_ID", "parcel_id")
    field_property_type: str = os.getenv("LA_FIELD_PROPERTY_TYPE", "property_type")
    city_filter_param: str = os.getenv("LA_CITY_FILTER_PARAM", "").strip()


LA_CONFIG = LAOpenDataConfig()


@dataclass(frozen=True, slots=True)
class BrowardBCPAConfig:
    dataset_url: str = os.getenv(
        "BROWARD_DATASET_URL",
        "https://services1.arcgis.com/fo4p3O1xXIiFqk9X/ArcGIS/rest/services/PropertyAppraiserParcels/FeatureServer/0/query",
    ).strip()
    page_size: int = int(os.getenv("BROWARD_PAGE_SIZE", "100"))
    city_filter_param: str = os.getenv("BROWARD_CITY_FILTER_PARAM", "CITY").strip()


BROWARD_CONFIG = BrowardBCPAConfig()


@dataclass(frozen=True, slots=True)
class OregonDeschutesConfig:
    dataset_url: str = os.getenv(
        "OR_DESCHUTES_DATASET_URL",
        "https://services1.arcgis.com/znO8Hz1SuVVohYhZ/ArcGIS/rest/services/Taxlots/FeatureServer/0/query",
    ).strip()
    related_url: str = os.getenv(
        "OR_DESCHUTES_RELATED_URL",
        "https://services1.arcgis.com/znO8Hz1SuVVohYhZ/ArcGIS/rest/services/Taxlots/FeatureServer/0/queryRelatedRecords",
    ).strip()
    page_size: int = int(os.getenv("OR_DESCHUTES_PAGE_SIZE", "200"))


OR_DESCHUTES_CONFIG = OregonDeschutesConfig()


@dataclass(frozen=True, slots=True)
class CaliforniaHumboldtConfig:
    dataset_url: str = os.getenv(
        "CA_HUMBOLDT_DATASET_URL",
        "https://gis.co.humboldt.ca.us/arcgis/rest/services/Accela_Parcels_Roads/MapServer/2/query",
    ).strip()
    page_size: int = int(os.getenv("CA_HUMBOLDT_PAGE_SIZE", "200"))
    city_filter_param: str = os.getenv("CA_HUMBOLDT_CITY_FILTER_PARAM", "SITCITY").strip()


CA_HUMBOLDT_CONFIG = CaliforniaHumboldtConfig()
