from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    latitude: float = Field(..., examples=[39.03])
    longitude: float = Field(..., examples=[-77.5])


class GeolocationResponse(BaseModel):
    ip: str = Field(..., examples=["8.8.8.8"])
    country: str = Field(..., examples=["United States"])
    country_code: str = Field(..., examples=["US"])
    region: str = Field(..., examples=["Virginia"])
    city: str = Field(..., examples=["Ashburn"])
    postal_code: str = Field(..., examples=["20149"])
    coordinates: Coordinates
    timezone: str = Field(..., examples=["America/New_York"])
    isp: str = Field(..., examples=["Google LLC"])
    organization: str = Field(..., examples=["AS15169 Google LLC"])
    provider: str = Field(..., examples=["ip-api"])
