from krita import Krita, DockWidgetFactory, DockWidgetFactoryBase
from .ai_api_diffusion_docker import AIDiffusionDocker

# Registrierung des Dockers in der Krita-Instanz
instance = Krita.instance()
instance.addDockWidgetFactory(
    DockWidgetFactory(
        "ai_api_diffusion_docker",
        DockWidgetFactoryBase.DockRight,
        AIDiffusionDocker
    )
)
