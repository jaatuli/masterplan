import os
import platform
import subprocess
from pathlib import Path


class SimulatorDisplay:
    """Simulaatio: tallentaa kuvan PNG:nä ja avaa sen oletuskuvakatselijalla."""

    OUTPUT_PATH = Path("output/dashboard.png")

    def show(self, image, open_preview: bool = False):
        self.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        image.save(self.OUTPUT_PATH)
        print(f"Kuva tallennettu: {self.OUTPUT_PATH.resolve()}")

        if open_preview:
            system = platform.system()
            if system == "Windows":
                os.startfile(str(self.OUTPUT_PATH))
            elif system == "Darwin":
                subprocess.Popen(["open", str(self.OUTPUT_PATH)])
            else:
                subprocess.Popen(["xdg-open", str(self.OUTPUT_PATH)])
