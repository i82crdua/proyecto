import os
import json
import cv2
import shutil
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.uix.colorpicker import ColorPicker
from zipfile import ZipFile

# Dirección IP de tu servidor EC2 y puerto
SERVER_URL = "http://15.237.190.22:8000/upload"

BASE_DIR = os.getcwd()
GENERIC_SAVE_DIR = os.path.join(BASE_DIR, "fotos")
PROFILE_FILE = os.path.join(BASE_DIR, "perfiles.json")
EMOTIONS_FILE = os.path.join(BASE_DIR, "emociones.json")

DEFAULT_EMOTIONS = {
    'felicidad': [1, 1, 0, 1],
    'tristeza': [0, 0, 1, 1],
    'enfado': [1, 0, 0, 1],
    'sorpresa': [1, 0.5, 0, 1]
}

def load_profiles():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r") as f:
            return json.load(f)
    return []

def save_profiles(profiles):
    with open(PROFILE_FILE, "w") as f:
        json.dump(profiles, f)

def load_emotions():
    if os.path.exists(EMOTIONS_FILE):
        with open(EMOTIONS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_emotions(emotions):
    with open(EMOTIONS_FILE, "w") as f:
        json.dump(emotions, f)

class StartScreen(Screen):
    def on_enter(self):
        self.load_profiles()

    def load_profiles(self):
        self.ids.profile_list.clear_widgets()
        profiles = load_profiles()
        layout = self.ids.profile_list

        for profile in profiles:
            row = BoxLayout(size_hint_y=None, height=40, spacing=10)

            btn = Button(text=profile, background_color=[0.5, 0.8, 1, 1])
            btn.bind(on_release=lambda x, p=profile: self.select_profile(p))

            del_btn = Button(text='🗑️', size_hint_x=None, width=40, background_color=[1, 0.4, 0.4, 1])
            del_btn.bind(on_release=lambda x, p=profile: self.delete_profile(p))

            row.add_widget(btn)
            row.add_widget(del_btn)
            layout.add_widget(row)

    def create_profile(self):
        name = self.ids.profile_input.text.strip()
        if name:
            profiles = load_profiles()
            if name not in profiles:
                profiles.append(name)
                save_profiles(profiles)
            App.get_running_app().current_profile = name
            self.manager.current = "main"

    def delete_profile(self, profile):
        profiles = load_profiles()
        if profile in profiles:
            profiles.remove(profile)
            save_profiles(profiles)

            emotions = load_emotions()
            if profile in emotions:
                del emotions[profile]
                save_emotions(emotions)

            self.load_profiles()

    def select_profile(self, profile_name):
        App.get_running_app().current_profile = profile_name
        self.manager.current = "main"

    def skip_profile(self):
        App.get_running_app().current_profile = None
        self.manager.current = "main"

    def export_data(self):
        # Genera nombre con fecha y hora
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_name = f"export_{timestamp}.zip"
        zip_path = os.path.join(BASE_DIR, zip_name)

        with ZipFile(zip_path, 'w') as zipf:
            for root, _, files in os.walk(GENERIC_SAVE_DIR):
                for f in files:
                    file_path = os.path.join(root, f)
                    arcname = os.path.relpath(file_path, BASE_DIR)
                    zipf.write(file_path, arcname)
            for f in [PROFILE_FILE, EMOTIONS_FILE]:
                if os.path.exists(f):
                    zipf.write(f, os.path.basename(f))

        try:
            with open(zip_path, 'rb') as f:
                response = requests.post(SERVER_URL, files={"file": f})
            if response.ok:
                self.show_popup("¡Datos exportados con éxito!")
            else:
                self.show_popup("Error al subir los datos al servidor.")
        except Exception:
            self.show_popup("Error al subir los datos al servidor.")

    def show_popup(self, message):
        popup = Popup(title="Exportar datos", size_hint=(0.8, 0.4))
        box = BoxLayout(orientation='vertical', spacing=10)
        label = Label(text=message)
        btn_close = Button(text="Cerrar", size_hint_y=0.2)
        btn_close.bind(on_release=popup.dismiss)
        box.add_widget(label)
        box.add_widget(btn_close)
        popup.content = box
        popup.open()

class MainScreen(Screen):
    pass

class CaptureScreen(Screen):
    def on_enter(self):
        self.load_buttons()
        self.start_camera()

    def get_save_dir(self):
        app = App.get_running_app()
        if app.current_profile:
            path = os.path.join(BASE_DIR, "fotos", app.current_profile)
        else:
            path = GENERIC_SAVE_DIR
        os.makedirs(path, exist_ok=True)
        return path

    def load_buttons(self):
        self.ids.emotion_grid.clear_widgets()
        app = App.get_running_app()
        emotions = DEFAULT_EMOTIONS.copy()

        custom = load_emotions().get(app.current_profile or "general", {})
        emotions.update(custom)

        self.ids.emotion_grid.cols = 2
        for emotion, color in emotions.items():
            btn = Button(text=emotion.capitalize(), background_color=color, size_hint_y=None, height=50)
            btn.bind(on_release=lambda x, e=emotion: self.capture_photo(e))
            self.ids.emotion_grid.add_widget(btn)

    def start_camera(self):
        self.capture = cv2.VideoCapture(0)
        Clock.schedule_interval(self.update_camera, 1.0 / 30.0)

    def update_camera(self, dt):
        ret, frame = self.capture.read()
        if ret:
            frame = cv2.flip(frame, 0)
            buf = frame.tobytes()
            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.ids.camera_feed.texture = texture

    def capture_photo(self, emotion):
        dir_path = os.path.join(self.get_save_dir(), emotion)
        os.makedirs(dir_path, exist_ok=True)
        ret, frame = self.capture.read()
        if ret:
            filename = f"{emotion}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = os.path.join(dir_path, filename)
            cv2.imwrite(file_path, frame)
            self.show_popup(f"Foto guardada en:\n{file_path}")

    def show_popup(self, message):
        popup = Popup(title="Resultado", size_hint=(0.8, 0.4))
        box = BoxLayout(orientation='vertical', spacing=10)
        label = Label(text=message)
        btn_close = Button(text="Cerrar", size_hint_y=0.2)
        btn_close.bind(on_release=popup.dismiss)
        box.add_widget(label)
        box.add_widget(btn_close)
        popup.content = box
        popup.open()

class NewEmotionScreen(Screen):
    def on_enter(self):
        self.load_buttons()

    def load_buttons(self):
        self.ids.new_emotion_grid.clear_widgets()
        app = App.get_running_app()
        emotions = load_emotions().get(app.current_profile or "general", {})

        self.ids.new_emotion_grid.cols = 2
        for emotion, color in emotions.items():
            row = BoxLayout(size_hint_y=None, height=50, spacing=10)
            btn = Button(text=emotion.capitalize(), background_color=color)
            del_btn = Button(text='🗑️', size_hint_x=None, width=40, background_color=[1, 0.4, 0.4, 1])
            del_btn.bind(on_release=lambda x, e=emotion: self.remove_emotion(e))
            row.add_widget(btn)
            row.add_widget(del_btn)
            self.ids.new_emotion_grid.add_widget(row)

    def add_custom_emotion(self):
        app = App.get_running_app()
        profile = app.current_profile or "general"
        emotions_data = load_emotions()
        emotions = emotions_data.get(profile, {})

        if len(emotions) >= 6:
            self.show_popup("Solo puedes añadir hasta 6 emociones personalizadas.")
            return

        box = BoxLayout(orientation='vertical', spacing=10)
        input_text = TextInput(hint_text="Nombre de la emoción", multiline=False)
        color_picker = ColorPicker()
        btn_save = Button(text="Guardar", size_hint=(1, None), height=40)

        def save_emotion(instance):
            new_emotion = input_text.text.strip().lower()
            if new_emotion and new_emotion not in DEFAULT_EMOTIONS and new_emotion not in emotions:
                color = color_picker.color[:3] + [1]
                emotions[new_emotion] = color
                emotions_data[profile] = emotions
                save_emotions(emotions_data)
                self.load_buttons()
                popup.dismiss()

        btn_save.bind(on_release=save_emotion)
        box.add_widget(input_text)
        box.add_widget(color_picker)
        box.add_widget(btn_save)

        popup = Popup(title="Nueva emoción", content=box, size_hint=(0.8, 0.8))
        popup.open()

    def remove_emotion(self, emotion):
        app = App.get_running_app()
        profile = app.current_profile or "general"
        emotions_data = load_emotions()
        if emotion in emotions_data.get(profile, {}):
            del emotions_data[profile][emotion]
            save_emotions(emotions_data)
            self.load_buttons()

    def show_popup(self, message):
        popup = Popup(title="Mensaje", size_hint=(0.8, 0.4))
        box = BoxLayout(orientation='vertical', spacing=10)
        label = Label(text=message)
        btn_close = Button(text="Cerrar", size_hint_y=0.2)
        btn_close.bind(on_release=popup.dismiss)
        box.add_widget(label)
        box.add_widget(btn_close)
        popup.content = box
        popup.open()

class MyApp(App):
    current_profile = None

    def build(self):
        Builder.load_file('myapp.kv')
        sm = ScreenManager()
        sm.add_widget(StartScreen(name="start"))
        sm.add_widget(MainScreen(name="main"))
        sm.add_widget(CaptureScreen(name="capture"))
        sm.add_widget(NewEmotionScreen(name="new_emotion"))
        return sm

if __name__ == "__main__":
    MyApp().run()
