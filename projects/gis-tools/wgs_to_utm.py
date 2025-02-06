# %%
import pyproj
from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info

def lat_lon_to_utm_easting_northing(lat, lon):
    """
    """
    utm_crs_info = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(
            west_lon_degree = lon, 
            south_lat_degree=lat,
            east_lon_degree=lon, 
            north_lat_degree=lat,
        )
    )[0]

    utm_crs = CRS.from_epsg(utm_crs_info.code)

    transformer = pyproj.Transformer.from_crs(
        CRS("EPSG:4326"),
        utm_crs,
        always_xy=True
    )

    easting, northing = transformer.transform(lon, lat)

    return easting, northing, utm_crs_info.name

# %% For Testing Purposes
lat, lon = 49.19743, -122.81588 #These represent the Surrey Office
easting, northing, utm_name = lat_lon_to_utm_easting_northing(lat, lon)
print(f"Easting: {easting}, Northing: {northing}, UTM Zone: {utm_name}")
# %%
