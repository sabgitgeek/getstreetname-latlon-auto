import pyodbc
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time


def connect_to_sql_server():
    """Establish connection to SQL Server"""
    conn = pyodbc.connect(
        'DRIVER={SQL Server};'
        'SERVER=192.169.0.2;'
        'DATABASE=MBJBSPOT_REPLICATION;'
        #'Trusted_Connection=yes;'  # Windows authentication
        # If using SQL authentication, use these instead:
         'UID=sa;'
         'PWD=2363194;'
    )
    return conn


def get_address_from_coordinates(latitude, longitude, geolocator):
    """Perform reverse geocoding with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            location = geolocator.reverse((latitude, longitude), exactly_one=True)
            if location:
                return location.raw['address']
            return None
        except (GeocoderTimedOut, GeocoderServiceError):
            if attempt == max_retries - 1:
                raise
            time.sleep(1)  # Wait before retrying


def main():
    try:
        # Initialize geocoder
        geolocator = Nominatim(user_agent="my_reverse_geocoder")

        # Connect to SQL Server
        conn = connect_to_sql_server()
        cursor = conn.cursor()

        # Fetch records that need geocoding
        cursor.execute("""
            SELECT parkingid, latitude, longitude 
            FROM [MBJBSPOT_REPLICATION].[dbo].[StreetFromLocation]
            WHERE loc_add = '' 
            AND latitude IS NOT NULL 
            AND longitude IS NOT NULL
        """)

        records = cursor.fetchall()

        # Process each record
        for record in records:
            parkingid, lat, lon = record
            try:
                # Get address from coordinates
                address_data = get_address_from_coordinates(lat, lon, geolocator)

                if address_data:
                    # Extract relevant address components
                    street = address_data.get('road', '')
                    house_number = address_data.get('house_number', '')
                    city = address_data.get('city', address_data.get('town', ''))
                    state = address_data.get('state', '')

                    # Construct full address and street
                    full_address = f"{house_number} {street}, {city}, {state}".strip()
                    street_name = f"{street}".strip()

                    # Update database
                    cursor.execute("""
                        UPDATE [MBJBSPOT_REPLICATION].[dbo].[StreetFromLocation]
                        SET 
                            loc_add = ?,
                            loc_street = ?
                        WHERE parkingid = ?
                    """, (full_address, street_name, parkingid))

                    conn.commit()
                    print(f"Updated record {parkingid} with address: {full_address}")

                    # Add delay to respect API rate limits
                    time.sleep(1)

            except Exception as e:
                print(f"Error processing record {parkingid}: {str(e)}")
                continue

    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    main()
