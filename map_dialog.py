import os
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Try importing folium
try:
    import folium
    logger.debug("Successfully imported folium")
except ImportError as e:
    logger.error(f"Failed to import folium: {str(e)}")
    raise ImportError("The 'folium' module is not installed. Please install it using 'pip install folium'.")

class MapDialog(QDialog):
    def __init__(self, lockers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Locker Location")
        self.setMinimumSize(800, 600)
        self.lockers = lockers
        logger.debug(f"Initializing MapDialog with {len(lockers)} lockers")

        # Buat peta
        map_file = self.create_map()
        if not map_file:
            logger.warning("No valid map file created")
            QMessageBox.warning(self, "Warning", "No valid location data available for the selected locker")
            self.close()
            return

        # Setup layout dan tampilkan peta
        layout = QVBoxLayout()
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl.fromLocalFile(os.path.abspath(map_file)))
        layout.addWidget(self.web_view)
        self.setLayout(layout)
        logger.debug("MapDialog UI setup completed")

    def create_map(self):
        if not self.lockers:
            logger.warning("No lockers provided for map creation")
            return None

        # Filter locker dengan koordinat valid
        valid_lockers = [
            locker for locker in self.lockers 
            if locker.get("latitude") is not None and locker.get("longitude") is not None 
            and isinstance(locker["latitude"], (int, float)) and isinstance(locker["longitude"], (int, float))
            and not (locker["latitude"] == 0 and locker["longitude"] == 0)
        ]
        if not valid_lockers:
            logger.warning("No valid coordinates found in lockers")
            return None

        # Hitung pusat peta berdasarkan rata-rata koordinat
        avg_lat = sum(locker["latitude"] for locker in valid_lockers) / len(valid_lockers)
        avg_lon = sum(locker["longitude"] for locker in valid_lockers) / len(valid_lockers)
        logger.debug(f"Map centered at latitude: {avg_lat}, longitude: {avg_lon}")

        # Inisialisasi peta
        try:
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=12)
        except Exception as e:
            logger.error(f"Failed to create Folium map: {str(e)}")
            return None

        # Tambahkan marker untuk setiap locker
        for locker in valid_lockers:
            try:
                folium.Marker(
                    [locker["latitude"], locker["longitude"]],
                    popup=f"Locker ID: {locker['lockerId']}<br>Status: {locker['status']}",
                    tooltip=locker["lockerId"]
                ).add_to(m)
                logger.debug(f"Added marker for locker {locker['lockerId']}")
            except Exception as e:
                logger.error(f"Failed to add marker for locker {locker['lockerId']}: {str(e)}")
                continue

        # Simpan peta sebagai file HTML sementara
        map_file = "lockers_map.html"
        try:
            m.save(map_file)
            logger.debug(f"Map saved to {map_file}")
            return map_file
        except Exception as e:
            logger.error(f"Failed to save map to {map_file}: {str(e)}")
            return None