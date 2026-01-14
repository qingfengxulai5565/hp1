from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.modalview import ModalView
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.core.window import Window
from kivy.uix.behaviors import ButtonBehavior
import os
import random
import json

# 设置窗口大小和背景颜色
Window.size = (400, 700)
Window.clearcolor = (0.1, 0.1, 0.18, 1)

# 尝试导入ID3标签解析库
try:
    from mutagen.mp3 import MP3

    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("Note: mutagen library not installed, MP3 metadata cannot be read")
    print("Please install: pip install mutagen")


# 创建带背景颜色的BoxLayout
class ColoredBoxLayout(BoxLayout):
    def __init__(self, bg_color=(0.1, 0.1, 0.18, 1), **kwargs):
        super(ColoredBoxLayout, self).__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.update_rect, size=self.update_rect)

    def update_rect(self, *args):
        if hasattr(self, 'rect'):
            self.rect.pos = self.pos
            self.rect.size = self.size


# 创建自定义组件
class AlbumArt(ButtonBehavior, Image):
    def __init__(self, **kwargs):
        super(AlbumArt, self).__init__(**kwargs)


class PlaylistButton(Button):
    def __init__(self, song_data, index, **kwargs):
        super(PlaylistButton, self).__init__(**kwargs)
        self.song_data = song_data
        self.index = index
        title = song_data.get('title', 'Unknown Song')
        artist = song_data.get('artist', 'Unknown Artist')
        self.text = f"{title}\n{artist}"
        self.font_size = 16
        self.halign = 'left'
        self.valign = 'center'
        self.text_size = (self.width, None)
        self.size_hint_y = None
        self.height = 70
        self.background_normal = ''
        self.background_color = (0.2, 0.2, 0.3, 1)  # 更亮的背景
        self.color = (1, 1, 1, 1)  # 白色文字
        self.markup = False  # 禁用markup

        self.bind(on_press=self.on_button_press)

    def on_button_press(self, instance):
        app = App.get_running_app()
        app.load_song(self.index)


class MusicPlayerApp(App):
    # 属性
    current_title = StringProperty("No Song Selected")
    current_artist = StringProperty("")
    current_time = StringProperty("00:00")
    total_time = StringProperty("00:00")
    progress_value = NumericProperty(0)
    is_playing = BooleanProperty(False)
    volume = NumericProperty(0.7)
    playlist = ListProperty([])  # 播放列表数据

    def build(self):
        # 创建主布局
        self.layout = ColoredBoxLayout(orientation='vertical', padding=10, spacing=10)

        # 状态栏
        self.status_bar = ColoredBoxLayout(size_hint=(1, 0.05), bg_color=(0.15, 0.15, 0.25, 1))
        status_label = Label(text="Harmony Player", font_size=14, color=(1, 1, 1, 1))
        self.status_label = Label(text="Songs: 0", font_size=14, color=(1, 1, 1, 1))
        volume_label = Label(text="Volume: 70%", font_size=14, color=(1, 1, 1, 1))
        self.status_bar.add_widget(status_label)
        self.status_bar.add_widget(self.status_label)
        self.status_bar.add_widget(volume_label)
        self.layout.add_widget(self.status_bar)

        # 顶部控制栏
        top_controls = BoxLayout(size_hint=(1, 0.08), spacing=10)

        self.add_btn = Button(text="Import Song", font_size=16,
                              background_normal='',
                              background_color=(0.3, 0.3, 0.4, 1),
                              color=(1, 1, 1, 1))
        self.add_btn.bind(on_press=self.show_file_chooser)

        self.import_folder_btn = Button(text="Import Folder", font_size=16,
                                        background_normal='',
                                        background_color=(0.3, 0.3, 0.4, 1),
                                        color=(1, 1, 1, 1))
        self.import_folder_btn.bind(on_press=self.import_music_folder)

        top_controls.add_widget(self.add_btn)
        top_controls.add_widget(self.import_folder_btn)
        self.layout.add_widget(top_controls)

        # 标题
        title = Label(text="Harmony Music Player", font_size=26, bold=True,
                      color=(0.98, 0.82, 0.13, 1), size_hint=(1, 0.08))
        self.layout.add_widget(title)

        # 专辑封面
        self.album_art = AlbumArt(size_hint=(1, 0.5))
        self.album_art.bind(on_press=self.on_album_click)

        # 创建一个默认专辑封面
        self.create_default_album_art()
        self.layout.add_widget(self.album_art)

        # 歌曲信息
        song_info = BoxLayout(orientation='vertical', size_hint=(1, 0.08))
        self.song_title = Label(text=self.current_title, font_size=20, bold=True,
                                color=(1, 1, 1, 1))
        self.song_artist = Label(text=self.current_artist, font_size=16,
                                 color=(0.8, 0.8, 0.8, 1))
        song_info.add_widget(self.song_title)
        song_info.add_widget(self.song_artist)
        self.layout.add_widget(song_info)

        # 进度条
        progress_box = BoxLayout(orientation='vertical', size_hint=(1, 0.08))
        self.progress_slider = Slider(min=0, max=100, value=self.progress_value,
                                      size_hint=(1, 0.7))
        self.progress_slider.bind(value=self.on_progress_change)

        time_box = BoxLayout(size_hint=(1, 0.3))
        self.current_time_label = Label(text=self.current_time, font_size=14,
                                        color=(0.8, 0.8, 0.8, 1), halign='left')
        self.total_time_label = Label(text=self.total_time, font_size=14,
                                      color=(0.8, 0.8, 0.8, 1), halign='right')
        time_box.add_widget(self.current_time_label)
        time_box.add_widget(self.total_time_label)

        progress_box.add_widget(self.progress_slider)
        progress_box.add_widget(time_box)
        self.layout.add_widget(progress_box)

        # 可视化效果
        self.visualizer = BoxLayout(size_hint=(1, 0.08), spacing=5, padding=10)
        self.bars = []
        for i in range(9):
            bar = BoxLayout(size_hint=(0.1, None))
            with bar.canvas:
                Color(0.9, 0.55, 0.2, 1)
                self.bar_rect = Rectangle(pos=bar.pos, size=bar.size)
            self.bars.append(bar)
            self.visualizer.add_widget(bar)
        self.layout.add_widget(self.visualizer)

        # 控制按钮
        controls = BoxLayout(size_hint=(1, 0.15), spacing=20, padding=(20, 0))

        self.shuffle_btn = Button(text="Shuffle", font_size=18,
                                  background_normal='',
                                  background_color=(0.3, 0.3, 0.4, 1),
                                  color=(1, 1, 1, 1))
        self.prev_btn = Button(text="Previous", font_size=18,
                               background_normal='',
                               background_color=(0.3, 0.3, 0.4, 1),
                               color=(1, 1, 1, 1))
        self.play_btn = Button(text="Play", font_size=24, bold=True,
                               background_normal='',
                               background_color=(0.9, 0.35, 0, 1),
                               color=(1, 1, 1, 1))
        self.next_btn = Button(text="Next", font_size=18,
                               background_normal='',
                               background_color=(0.3, 0.3, 0.4, 1),
                               color=(1, 1, 1, 1))
        self.repeat_btn = Button(text="Repeat", font_size=18,
                                 background_normal='',
                                 background_color=(0.3, 0.3, 0.4, 1),
                                 color=(1, 1, 1, 1))

        self.prev_btn.bind(on_press=self.prev_song)
        self.play_btn.bind(on_press=self.toggle_play)
        self.next_btn.bind(on_press=self.next_song)
        self.shuffle_btn.bind(on_press=self.shuffle_playlist)
        self.repeat_btn.bind(on_press=self.toggle_repeat)

        controls.add_widget(self.shuffle_btn)
        controls.add_widget(self.prev_btn)
        controls.add_widget(self.play_btn)
        controls.add_widget(self.next_btn)
        controls.add_widget(self.repeat_btn)
        self.layout.add_widget(controls)

        # 播放列表按钮
        playlist_btn = Button(text="Playlist", font_size=18,
                              size_hint=(1, 0.1),
                              background_normal='',
                              background_color=(0.3, 0.3, 0.4, 1),
                              color=(1, 1, 1, 1))
        playlist_btn.bind(on_press=self.show_playlist)
        self.layout.add_widget(playlist_btn)

        # 初始化音乐数据
        self.current_index = 0
        self.sound = None
        self.song_length = 0
        self.repeat_mode = False  # False: 不循环, True: 单曲循环

        # 音量控制
        self.volume_slider = Slider(min=0, max=1, value=0.7, size_hint=(0.3, 1))
        self.volume_slider.bind(value=self.set_volume)

        # 尝试从配置文件加载播放列表
        self.load_playlist_from_config()

        # 启动可视化更新
        Clock.schedule_interval(self.update_visualizer, 0.2)

        # 更新状态栏
        self.update_status_bar()

        return self.layout

    def create_default_album_art(self):
        # 设置默认颜色
        self.album_art.color = (0.15, 0.15, 0.35, 1)

    def set_volume(self, instance, value):
        self.volume = value
        if self.sound:
            self.sound.volume = value
        self.update_status_bar()

    def load_playlist_from_config(self):
        # 尝试从配置文件加载播放列表
        config_file = "playlist.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.playlist = json.load(f)
                print(f"Loaded {len(self.playlist)} songs from config")
                # 如果有歌曲，加载第一首
                if self.playlist:
                    self.load_song(0)
            except Exception as e:
                print(f"Failed to load config: {e}")
                self.playlist = []
        else:
            self.playlist = []

    def save_playlist_to_config(self):
        # 保存播放列表到配置文件
        try:
            with open("playlist.json", 'w', encoding='utf-8') as f:
                json.dump(self.playlist, f, ensure_ascii=False, indent=2)
            print("Playlist saved")
        except Exception as e:
            print(f"Failed to save playlist: {e}")

    def update_status_bar(self):
        # 更新状态栏显示
        if hasattr(self, 'status_label'):
            status_text = f"Songs: {len(self.playlist)}"
            if self.playlist and self.current_index < len(self.playlist):
                status_text += f" | Current: {self.current_index + 1}/{len(self.playlist)}"
            self.status_label.text = status_text

            # 更新音量显示
            volume_percent = int(self.volume * 100)
            if hasattr(self, 'status_bar') and len(self.status_bar.children) > 2:
                self.status_bar.children[0].text = f"Volume: {volume_percent}%"

    def get_mp3_info(self, filepath):
        """获取MP3文件的元数据"""
        try:
            if HAS_MUTAGEN:
                # 读取音频文件信息
                audio = MP3(filepath)

                # 获取时长
                duration_sec = audio.info.length
                minutes = int(duration_sec // 60)
                seconds = int(duration_sec % 60)
                duration = f"{minutes:02d}:{seconds:02d}"

                # 尝试获取标题和艺术家信息
                title = ""
                artist = ""

                # 从标签中获取信息
                if hasattr(audio, 'tags'):
                    tags = audio.tags
                    if 'TIT2' in tags:
                        title = str(tags['TIT2'])
                    if 'TPE1' in tags:
                        artist = str(tags['TPE1'])

                # 如果没有获取到标题，使用文件名
                if not title:
                    title = os.path.basename(filepath).replace('.mp3', '').replace('.MP3', '')

                return {
                    'title': title,
                    'artist': artist or 'Unknown Artist',
                    'duration': duration,
                    'path': filepath,
                    'length': duration_sec
                }
            else:
                # 如果没有mutagen，使用文件名作为标题
                filename = os.path.basename(filepath)
                title = filename.replace('.mp3', '').replace('.MP3', '')
                return {
                    'title': title,
                    'artist': 'Unknown Artist',
                    'duration': '03:00',
                    'path': filepath,
                    'length': 180  # 默认3分钟
                }
        except Exception as e:
            print(f"Failed to read MP3 file info {filepath}: {e}")
            filename = os.path.basename(filepath)
            title = filename.replace('.mp3', '').replace('.MP3', '')
            return {
                'title': title,
                'artist': 'Unknown Artist',
                'duration': '03:00',
                'path': filepath,
                'length': 180  # 默认3分钟
            }

    def add_songs(self, filepaths):
        """添加歌曲到播放列表"""
        added_count = 0
        for filepath in filepaths:
            # 检查文件是否已经是MP3格式
            if filepath.lower().endswith('.mp3'):
                # 获取歌曲信息
                song_info = self.get_mp3_info(filepath)

                # 检查是否已在播放列表中
                existing = False
                for song in self.playlist:
                    if song['path'] == filepath:
                        existing = True
                        break

                if not existing:
                    self.playlist.append(song_info)
                    added_count += 1
                    print(f"Added song: {song_info['title']} - {song_info['artist']}")

        if added_count > 0:
            # 保存播放列表
            self.save_playlist_to_config()

            # 更新状态栏
            self.update_status_bar()

            # 如果当前没有播放歌曲，播放第一首
            if not self.playlist or self.current_index >= len(self.playlist):
                self.load_song(0)

        return added_count

    def show_file_chooser(self, instance):
        """显示文件选择器"""
        print("Showing file chooser...")
        modal = ModalView(size_hint=(0.9, 0.8), auto_dismiss=True)

        # 主容器
        container = ColoredBoxLayout(orientation='vertical', spacing=10, padding=10, bg_color=(0.1, 0.1, 0.18, 1))

        # 标题
        title = Label(text="Select Music Files", font_size=24, bold=True,
                      color=(0.98, 0.82, 0.13, 1), size_hint=(1, 0.1))
        container.add_widget(title)

        # 文件选择器
        filechooser = FileChooserListView(
            path=os.path.expanduser("~"),
            filters=['*.mp3'],
            multiselect=True
        )

        # 按钮栏
        button_box = BoxLayout(size_hint=(1, 0.1), spacing=10)

        cancel_btn = Button(text="Cancel", font_size=18,
                            background_normal='',
                            background_color=(0.3, 0.3, 0.4, 1),
                            color=(1, 1, 1, 1))
        cancel_btn.bind(on_press=lambda x: modal.dismiss())

        add_btn = Button(text="Add Selected", font_size=18,
                         background_normal='',
                         background_color=(0.9, 0.35, 0, 1),
                         color=(1, 1, 1, 1))

        def add_selected_files(instance):
            selected = filechooser.selection
            if selected:
                added = self.add_songs(selected)
                modal.dismiss()

                # 显示添加结果
                self.show_message(f"Added {added} songs")
            else:
                self.show_message("Please select files first")

        add_btn.bind(on_press=add_selected_files)

        button_box.add_widget(cancel_btn)
        button_box.add_widget(add_btn)

        container.add_widget(filechooser)
        container.add_widget(button_box)

        modal.add_widget(container)
        modal.open()

    def import_music_folder(self, instance):
        """导入整个文件夹的音乐文件"""
        print("Showing folder chooser...")
        modal = ModalView(size_hint=(0.9, 0.8), auto_dismiss=True)

        # 主容器
        container = ColoredBoxLayout(orientation='vertical', spacing=10, padding=10, bg_color=(0.1, 0.1, 0.18, 1))

        # 标题
        title = Label(text="Select Music Folder", font_size=24, bold=True,
                      color=(0.98, 0.82, 0.13, 1), size_hint=(1, 0.1))
        container.add_widget(title)

        # 文件夹选择器
        dirchooser = FileChooserListView(
            path=os.path.expanduser("~"),
            dirselect=True
        )

        # 按钮栏
        button_box = BoxLayout(size_hint=(1, 0.1), spacing=10)

        cancel_btn = Button(text="Cancel", font_size=18,
                            background_normal='',
                            background_color=(0.3, 0.3, 0.4, 1),
                            color=(1, 1, 1, 1))
        cancel_btn.bind(on_press=lambda x: modal.dismiss())

        import_btn = Button(text="Import Folder", font_size=18,
                            background_normal='',
                            background_color=(0.9, 0.35, 0, 1),
                            color=(1, 1, 1, 1))

        def import_folder_files(instance):
            selected = dirchooser.selection
            if selected and os.path.isdir(selected[0]):
                folder_path = selected[0]

                # 查找文件夹中的所有MP3文件
                mp3_files = []
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        if file.lower().endswith('.mp3'):
                            mp3_files.append(os.path.join(root, file))

                if mp3_files:
                    added = self.add_songs(mp3_files)
                    modal.dismiss()
                    self.show_message(f"Imported {added} songs from folder")
                else:
                    self.show_message("No MP3 files found in folder")
            else:
                self.show_message("Please select a folder first")

        import_btn.bind(on_press=import_folder_files)

        button_box.add_widget(cancel_btn)
        button_box.add_widget(import_btn)

        container.add_widget(dirchooser)
        container.add_widget(button_box)

        modal.add_widget(container)
        modal.open()

    def show_message(self, message):
        """显示消息提示"""
        modal = ModalView(size_hint=(0.6, 0.3), auto_dismiss=True)

        container = ColoredBoxLayout(orientation='vertical', spacing=10, padding=20, bg_color=(0.1, 0.1, 0.18, 1))

        label = Label(text=message, font_size=18, color=(1, 1, 1, 1))
        ok_btn = Button(text="OK", font_size=18,
                        background_normal='',
                        background_color=(0.9, 0.35, 0, 1),
                        color=(1, 1, 1, 1),
                        size_hint=(1, 0.4))
        ok_btn.bind(on_press=lambda x: modal.dismiss())

        container.add_widget(label)
        container.add_widget(ok_btn)

        modal.add_widget(container)

        # 3秒后自动关闭
        Clock.schedule_once(lambda dt: modal.dismiss(), 3)

        modal.open()

    def load_song(self, index):
        if not self.playlist or index < 0 or index >= len(self.playlist):
            return

        self.current_index = index
        song = self.playlist[index]

        # 停止当前播放
        if self.sound:
            self.sound.stop()
            self.sound = None

        # 更新UI
        self.current_title = song["title"]
        self.current_artist = song["artist"]
        self.total_time = song["duration"]

        # 更新状态栏
        self.update_status_bar()

        # 重置进度
        self.progress_value = 0
        self.current_time = "00:00"
        self.song_length = song.get("length", 180)

        # 尝试加载音频文件
        try:
            self.sound = SoundLoader.load(song['path'])
            if self.sound:
                self.sound.volume = self.volume
                print(f"Audio loaded: {song['path']}")
            else:
                print(f"Failed to load audio: {song['path']}")
        except Exception as e:
            print(f"Error loading audio: {e}")
            self.sound = None

        # 更新播放按钮状态
        if self.sound:
            self.play_btn.text = "Play"
            self.is_playing = False
        else:
            self.play_btn.text = "Play"
            self.is_playing = False

        print(f"Loaded song: {song['title']} - {song['artist']}")

    def toggle_play(self, instance):
        if not self.playlist:
            self.show_message("Playlist is empty, please import songs first")
            return

        if self.current_index >= len(self.playlist):
            self.load_song(0)
            return

        if not self.sound:
            # 如果没有音频，重新加载
            self.load_song(self.current_index)

        if not self.sound:
            self.show_message("Failed to load audio file")
            return

        if self.is_playing:
            # 暂停播放
            self.sound.stop()
            self.is_playing = False
            self.play_btn.text = "Play"
            print("Music paused")
        else:
            # 开始播放
            self.sound.play()
            self.is_playing = True
            self.play_btn.text = "Pause"
            print("Playing music")

            # 开始更新进度
            if hasattr(self, 'progress_event'):
                Clock.unschedule(self.progress_event)
            self.progress_event = Clock.schedule_interval(self.update_progress, 0.5)

    def update_progress(self, dt):
        if self.is_playing and self.sound:
            # 获取当前播放位置（SoundLoader没有直接获取当前位置的方法）
            # 所以我们模拟进度
            if self.song_length > 0:
                # 简单模拟：每0.5秒增加一定百分比
                increment = 100 * dt / self.song_length
                self.progress_value = min(self.progress_value + increment, 100)

                # 更新时间显示
                current_seconds = int(self.progress_value / 100 * self.song_length)
                minutes = current_seconds // 60
                seconds = current_seconds % 60
                self.current_time = f"{minutes:02d}:{seconds:02d}"

                # 如果到达结尾，根据循环模式处理
                if self.progress_value >= 100:
                    if self.repeat_mode:
                        # 单曲循环
                        self.progress_value = 0
                        self.sound.seek(0)
                        self.sound.play()
                    else:
                        # 播放下一首
                        self.next_song()

    def on_progress_change(self, instance, value):
        # 在实际应用中，这里会设置音频的播放位置
        current_seconds = int(value / 100 * self.song_length)
        minutes = current_seconds // 60
        seconds = current_seconds % 60
        self.current_time = f"{minutes:02d}:{seconds:02d}"

        # 如果正在播放，跳转到指定位置
        if self.is_playing and self.sound and hasattr(self.sound, 'seek'):
            try:
                self.sound.seek(current_seconds)
            except:
                pass

    def prev_song(self, instance=None):
        if not self.playlist:
            return

        new_index = (self.current_index - 1) % len(self.playlist)
        self.load_song(new_index)

    def next_song(self, instance=None):
        if not self.playlist:
            return

        new_index = (self.current_index + 1) % len(self.playlist)
        self.load_song(new_index)

    def shuffle_playlist(self, instance):
        # 随机播放
        if self.playlist:
            new_index = random.randint(0, len(self.playlist) - 1)
            self.load_song(new_index)
            print("Shuffle play")

    def toggle_repeat(self, instance):
        self.repeat_mode = not self.repeat_mode
        if self.repeat_mode:
            self.repeat_btn.background_color = (0.9, 0.35, 0, 1)  # 橙色
            print("Repeat on")
        else:
            self.repeat_btn.background_color = (0.3, 0.3, 0.4, 1)  # 深蓝色
            print("Repeat off")

    def update_visualizer(self, dt):
        for i, bar in enumerate(self.bars):
            # 如果正在播放，显示动态效果；否则显示静态效果
            if self.is_playing:
                # 使可视化效果更自然，根据位置有不同的基础高度
                base_height = 0.1 + 0.3 * (i / 9)
                variation = random.uniform(0, 0.6)
                height = base_height + variation
            else:
                height = 0.1  # 播放暂停时显示低高度

            bar.size_hint_y = height
            bar.canvas.before.clear()
            with bar.canvas.before:
                # 根据高度设置颜色
                if height > 0.8:
                    Color(0.9, 0.35, 0, 1)  # 橙色
                elif height > 0.5:
                    Color(0.9, 0.55, 0.2, 1)  # 黄色
                else:
                    Color(0.9, 0.7, 0.3, 1)  # 浅黄色

                # 绘制矩形
                Rectangle(pos=bar.pos, size=(bar.width, bar.height * height))

    def show_playlist(self, instance):
        """显示播放列表"""
        if not self.playlist:
            self.show_message("Playlist is empty, please import songs first")
            return

        # 创建播放列表弹窗
        modal = ModalView(size_hint=(0.9, 0.8), auto_dismiss=True)

        # 主容器
        container = ColoredBoxLayout(orientation='vertical', spacing=10, padding=10, bg_color=(0.1, 0.1, 0.18, 1))

        # 标题和统计信息
        title_box = BoxLayout(size_hint=(1, 0.1))
        title = Label(text=f"Playlist ({len(self.playlist)} songs)", font_size=24, bold=True,
                      color=(0.98, 0.82, 0.13, 1))

        clear_btn = Button(text="Clear All", font_size=14,
                           background_normal='',
                           background_color=(0.9, 0.2, 0.2, 1),
                           color=(1, 1, 1, 1),
                           size_hint=(0.3, 1))
        clear_btn.bind(on_press=self.clear_playlist)

        title_box.add_widget(title)
        title_box.add_widget(clear_btn)
        container.add_widget(title_box)

        # 滚动视图
        scroll = ScrollView(size_hint=(1, 0.9))
        playlist_layout = GridLayout(cols=1, spacing=5, size_hint_y=None)
        playlist_layout.bind(minimum_height=playlist_layout.setter('height'))

        # 添加播放列表项
        for i, song in enumerate(self.playlist):
            btn = PlaylistButton(song_data=song, index=i)

            # 如果是当前歌曲，高亮显示
            if i == self.current_index:
                btn.background_color = (0.9, 0.35, 0, 0.7)

            playlist_layout.add_widget(btn)

        scroll.add_widget(playlist_layout)
        container.add_widget(scroll)

        modal.add_widget(container)
        modal.open()

    def clear_playlist(self, instance):
        """清空播放列表"""
        self.playlist = []
        self.save_playlist_to_config()
        self.update_status_bar()
        self.current_index = 0
        self.current_title = "No Song Selected"
        self.current_artist = ""
        self.total_time = "00:00"
        self.progress_value = 0

        # 停止播放
        if self.sound:
            self.sound.stop()
            self.sound = None

        # 关闭播放列表弹窗
        for child in self.layout.walk():
            if isinstance(child, ModalView):
                child.dismiss()

        self.show_message("Playlist cleared")

    def on_album_click(self, instance):
        # 点击专辑封面时切换播放/暂停
        self.toggle_play(instance)

    def on_stop(self):
        # 停止播放
        if self.sound:
            self.sound.stop()

        # 保存播放列表
        self.save_playlist_to_config()

        # 取消所有定时器
        if hasattr(self, 'progress_event'):
            Clock.unschedule(self.progress_event)

        return super().on_stop()


if __name__ == '__main__':
    # 创建资源目录（如果不存在）
    if not os.path.exists('assets'):
        os.makedirs('assets')

    print("Starting Harmony Music Player...")
    print("Note: This version uses Kivy's SoundLoader for actual audio playback.")
    print("Make sure your audio files are in MP3 format and your system supports them.")

    # 运行应用
    app = MusicPlayerApp()
    app.run()