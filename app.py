from flask import Flask, render_template, request, send_file
import pandas as pd
import gdown
import folium
from io import BytesIO
from simplekml import Kml, Camera
import utm
import tempfile
import math
import os

app = Flask(__name__)

def get_panther_data():
    file_id = '1iQIVDFPRvxqJ2xDbQFwU9MZAS_KL9tt3'
    url = f'https://drive.google.com/uc?id={file_id}'
    output = 'panther_data.csv'
    gdown.download(url, output, quiet=False)
    df = pd.read_csv(output)

    latitudes, longitudes = [], []
    for easting, northing in zip(df['UTM83EAST'], df['UTM83NORTH']):
        lat, lon = utm.to_latlon(easting, northing, 17, 'R')
        latitudes.append(lat)
        longitudes.append(lon)

    df['Latitude'] = latitudes
    df['Longitude'] = longitudes
    return df

@app.route('/', methods=['GET', 'POST'])
def home():
    df = get_panther_data()
    panther_ids = df['CATNUMBER'].unique()
    selected_panther = request.form.get('panther_id') if request.method == 'POST' else panther_ids[0]
    filtered_df = df[df['CATNUMBER'] == selected_panther]

    folium_map = folium.Map(location=[filtered_df['Latitude'].iloc[0], filtered_df['Longitude'].iloc[0]], zoom_start=10)
    for _, row in filtered_df.iterrows():
        folium.Marker([row['Latitude'], row['Longitude']],
                      popup=f"Date: {row['FLGTDATE']}, Time: {row['TIME']}").add_to(folium_map)
    map_html = folium_map._repr_html_()

    return render_template('index.html', panther_ids=panther_ids, selected_panther=selected_panther, map_html=map_html)

@app.route('/download_kml/<panther_id>')
def download_kml(panther_id):
    df = get_panther_data()
    filtered_df = df[df['CATNUMBER'] == panther_id]
    kml = Kml()

    altitude = 100
    tilt = 80
    flyto_duration = 5

    tour = kml.newgxtour(name="Panther Telemetry Tour")
    playlist = tour.newgxplaylist()
    point_counter = 1

    for i in range(len(filtered_df) - 1):
        row_current = filtered_df.iloc[i]
        row_next = filtered_df.iloc[i + 1]

        delta_longitude = row_next['Longitude'] - row_current['Longitude']
        delta_latitude = row_next['Latitude'] - row_current['Latitude']
        heading = math.degrees(math.atan2(delta_longitude, delta_latitude)) % 360

        orientation_camera = Camera(
            longitude=row_current['Longitude'],
            latitude=row_current['Latitude'],
            altitude=altitude,
            altitudemode="relativeToGround",
            tilt=tilt,
            heading=heading
        )

        orient_flyto = playlist.newgxflyto(gxduration=1)
        orient_flyto.camera = orientation_camera

        move_camera = Camera(
            longitude=row_next['Longitude'],
            latitude=row_next['Latitude'],
            altitude=altitude,
            altitudemode="relativeToGround",
            tilt=tilt,
            heading=heading
        )

        move_flyto = playlist.newgxflyto(gxduration=flyto_duration)
        move_flyto.camera = move_camera

        kml.newpoint(name=str(point_counter),
                     coords=[(row_current['Longitude'], row_current['Latitude'])],
                     description=f"FLGTDATE: {row_current['FLGTDATE']}, CATNUMBER: {row_current['CATNUMBER']}, AGENCY: {row_current['AGENCY']}, TIME: {row_current['TIME']}")
        point_counter += 1

    last_row = filtered_df.iloc[-1]
    kml.newpoint(name=str(point_counter),
                 coords=[(last_row['Longitude'], last_row['Latitude'])],
                 description=f"FLGTDATE: {last_row['FLGTDATE']}, CATNUMBER: {last_row['CATNUMBER']}, AGENCY: {last_row['AGENCY']}, TIME: {last_row['TIME']}")

    # Save the KML file to a temporary fixed location
    kml_file_path = f"panther_{panther_id}_telemetry_tour.kml"
    kml.save(kml_file_path)

    # Serve the file and delete it after download
    try:
        return send_file(kml_file_path, as_attachment=True, download_name=kml_file_path, mimetype="application/vnd.google-earth.kml+xml")
    finally:
        # Remove the file after sending
        os.remove(kml_file_path)

if __name__ == '__main__':
    app.run(debug=True)
