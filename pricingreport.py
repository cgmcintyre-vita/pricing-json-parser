from SAPCCReport import SAPCCExportReport
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pydantic import BaseModel, model_validator, RootModel, Field, ConfigDict, field_validator
from typing import Self, Optional
from pydantic_core import ValidationError

class Country(Enum):
    # Note, this is currently only designed for AMER
    CA = "ca"
    US = "us"


class PriceInfo(BaseModel):
    '''
    Represents pricing information for a product in a specific region.
    
    Handles both regular and sale pricing with automatic validation and 
    precision control for monetary values. Empty strings in source data
    are automatically converted to None for missing pricing.
    
    Attributes:
        salePrice: The discounted price, None if no sale price available
        price: The regular/list price, None if no pricing available
        
    '''
    salePrice: Optional[Decimal] = Field(default = None, decimal_places=2)
    price:Optional[Decimal] = Field(default = None, decimal_places=2)

    @field_validator('price', 'salePrice', mode='before')
    @classmethod
    def empty_string_to_none(cls, v:str | None) -> str | None:
        if v == "" or v is None:
            return None
        else:
            return v
        
    def discount_percentage(self) -> Optional[Decimal]:
        """
        Calculate the discount percentage from regular price to sale price.
        
        Returns:
            Decimal rounded to 2 decimal places, or None if pricing unavailable
        """
        if self.salePrice is None or self.price is None or self.price == 0:
            return None
        discount = (1 - self.salePrice / self.price) * 100
        return discount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def savings_amount(self) -> Optional[Decimal]:
        """
        Calculate the absolute savings amount (regular price - sale price).
        
        Returns:
            Decimal amount saved, or None if pricing unavailable
        """
        if self.salePrice is None or self.price is None:
            return None
        return self.price - self.salePrice
    
    def has_pricing(self) -> bool:
        """
        Check if both regular and sale pricing are available.
        
        Returns:
            True if both prices are set, False otherwise
        """
        return self.salePrice is not None and self.price is not None

class ProductPricing(RootModel[dict[str, PriceInfo]]):
    '''
    Container for product pricing across multiple countries/regions.
    
    Parses JSON data where country codes are keys and pricing objects are values.
    Handles missing or empty pricing data gracefully by setting values to None.
    
    The root attribute contains a dictionary mapping country codes to PriceInfo objects.
    
    Example:
        >>> json_data = '{"us":{"salePrice":"99.50","price":"129.99"},"ca":{"salePrice":"","price":""}}'
        >>> pricing = ProductPricing.model_validate_json(json_data)
        >>> pricing.root['us'].discount_percentage()
        Decimal('23.46')
        >>> pricing.root['ca'].has_pricing()
        False
        
    Note:
        Access pricing data via .root['country_code'] since this uses RootModel.
        Countries with empty pricing strings will have None values for prices.
    '''
    pass

@dataclass(slots=True)
class CountryPrice:
    '''
    Contains the pricing from the file
    '''
    sku:str
    price: Optional[Decimal]
    sale_price: Optional[Decimal]
    country: Country

class MissingCountryError(ValueError):
    ...

class WrongSKUError(ValueError):
    ...

class ItemPrice(BaseModel):
    model_config = ConfigDict(frozen=True)
    sku:str | int
    prices:dict[Country, CountryPrice]

    @model_validator(mode="after")
    def validate_prices(self) -> Self:
        for price in self.prices.values():
            if price.sku != self.sku:
                raise WrongSKUError(f"Incorrect pricing sent for {self.sku}")
        if len(self.prices) != len(Country):
            raise MissingCountryError(f"Missing price for {self.sku}: {self.prices}")
        return self
    
    def _price_or_zero(self, price:Optional[Decimal]) -> str:
        ''' returns "0" if an optional price is None, else returns str of the price'''
        return str(price) if price else "0"
        
    @property
    def output_str_value(self) -> list[str | float]:
        ''' 
        returns the string values of the prices in the following order:

        "SKU", "US Price", "US Sale Price", "CA Price", "CA Sale Price"
        '''

        return [
            str(self.sku),
            float(self._price_or_zero(self.prices[Country.US].price)),
            float(self._price_or_zero(self.prices[Country.US].sale_price)),
            float(self._price_or_zero(self.prices[Country.CA].price)),
            float(self._price_or_zero(self.prices[Country.CA].sale_price))
        ]
class PricingFile(SAPCCExportReport):
    '''
    Product sheet exported from SAP CC that has the following columns, in order:
    Catalog version*^
    Name[en]
    Price in Json
    Product ID*^
    
    As with other SAP CX reports, the data should start on line 4'''

    CATALOG_COL = 0
    NAME_COL = 1
    JSON_PRICE_COL = 2
    SKU_COL = 3

    @staticmethod
    def get_pricing_from_JSON(json_str:str, sku:str) -> dict[Country, CountryPrice]:
        try:
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
        except ValidationError as e:
            print(f"Received the following invalid json: {json_str}")
            raise e

            
class AMERPricingFile(PricingFile):
    '''
    Product sheet exported from SAP CC that has the following columns, in order:
    Catalog version*^
    Name[en]
    Price in Json
    Product ID*^
    
    As with other SAP CX reports, the data should start on line 4

    AMER specific implementation. 
    '''

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
