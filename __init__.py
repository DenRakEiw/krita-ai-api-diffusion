import traceback
import os
from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase

def setup_plugin():
    log_path = os.path.join(os.path.dirname(__file__), "debug.log")
    with open(log_path, "w") as f:
        f.write("Starte Plugin-Ladevorgang...\n")
        try:
            from .ai_api_diffusion_docker import AIDiffusionDocker
            
            instance = Krita.instance()
            DOCKER_ID = 'ai_api_diffusion_docker'
            
            factory = DockWidgetFactory(
                DOCKER_ID,
                DockWidgetFactoryBase.DockRight,
                AIDiffusionDocker
            )
            instance.addDockWidgetFactory(factory)
            f.write("AI API Diffusion Plugin erfolgreich registriert.\n")
            
        except Exception as e:
            f.write("FEHLER beim Laden:\n")
            f.write(traceback.format_exc())
            print("Fehler beim Laden des AI API Diffusion Plugins (siehe debug.log)")

setup_plugin()
