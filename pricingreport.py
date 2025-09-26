from SAPCCReport import SAPCCExportReport
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from pydantic import BaseModel, model_validator, RootModel, Field
from typing import Self, Optional

class Country(Enum):
    # Note, this is currently only designed for AMER
    CA = "ca"
    US = "us"


class PriceInfo(BaseModel):
    salePrice: Optional[Decimal] = Field(decimal_places=2)
    price:Optional[Decimal] = Field(decimal_places=2)

class ProductPricing(RootModel[dict[str, PriceInfo]]):
    pass

@dataclass(slots=True)
class CountryPrice:
    sku:str
    price: Optional[Decimal]
    sale_price: Optional[Decimal]
    country: Country

class MissingCountryError(ValueError):
    ...

class WrongSKUError(ValueError):
    ...

class ItemPrice(BaseModel):
    sku:str
    prices:dict[Country, CountryPrice]

    @model_validator(mode="after")
    def validate_prices(self) -> Self:
        for price in self.prices.values():
            if price.sku != self.sku:
                raise WrongSKUError(f"Incorrect pricing sent for {self.sku}")
        if len(self.prices) != len(Country):
            raise MissingCountryError(f"Missing price for {self.sku}: {self.prices}")
        return self
        
class PricingFile(SAPCCExportReport):
    CATALOG_COL = 1
    NAME_COL = 2
    JSON_PRICE_COL = 3
    SKU_COL = 4

    @staticmethod
    def get_pricing_from_JSON(json_str:str, sku:str) -> dict[Country, CountryPrice]:
        prices = ProductPricing.model_validate_json(json_str)
        countryprices:dict[Country, CountryPrice] = {}
        for country in Country:
            countryprices[country] = CountryPrice(
                sku=sku,
                price=prices.root[country.value].price,
                sale_price=prices.root[country.value].salePrice,
                country=country
            )
        return countryprices

            
class AMERPricingFile(PricingFile):

    def get_prices(self) -> list[ItemPrice]:
        item_prices:list[ItemPrice] = []
        ws = self._get_ws(self._report_file)
        for row in ws.iter_rows(min_row=self.data_starting_row):
            sku = str(row[self.SKU_COL].value)
            country_prices = self.get_pricing_from_JSON(str(row[self.JSON_PRICE_COL].value), sku)
            item_prices.append(ItemPrice(
                sku=sku,
                prices = country_prices
                )
            )
        return item_prices
