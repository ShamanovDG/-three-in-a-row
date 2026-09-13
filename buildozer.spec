[app]

# Название, которое увидит пользователь на телефоне
title = Match 3

# Только латиница, цифры и подчёркивания, без пробелов
package.name = match3

# Замени vboxuser на свой ник/название разработчика латиницей
package.domain = org.vboxuser

# В этой папке должен находиться main.py
source.dir = .

# Файлы, которые нужно положить в APK
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,ttf,otf,mp3,wav,ogg,db,sqlite,sqlite3

# Не включать кэши и виртуальные окружения в APK
source.exclude_dirs = .git,.buildozer,bin,venv,venv_p4a_develop,__pycache__,.idea,.vscode

# Нужные Python-модули:
# sqlite3, copy, datetime, random входят в Python и отдельно не указываются
requirements = python3,kivy,android,pyjnius,sqlite3

# Версия приложения
version = 0.1

# Ориентация: portrait, landscape или all
orientation = portrait

# 0 — с системной панелью, 1 — полноэкранное приложение
fullscreen = 0


# ---------- Android ----------

# Для Python 3.14 нельзя ставить ниже 24:
# иначе не найдутся preadv/pwritev во время сборки CPython
android.minapi = 24

# Target Android SDK
android.api = 35

android.add_gradle_repositories = "mavenCentral()"
android.gradle_dependencies = com.yandex.android:mobileads:8.1.0
# Версия Android NDK
android.ndk = 28c

# Development-ветка необходима для Python 3.14
p4a.branch = develop

# Сборка для большинства современных Android-устройств
android.archs = arm64-v8a,armeabi-v7a

# Разрешения, необходимые KivMob/AdMob для загрузки рекламы
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# Логи Python через adb logcat
android.logcat_filters = *:S python:D

# Если KivMob потребует AndroidX, поменяй False на True
android.enable_androidx = True

# Пока используются TestIds из твоего кода — App ID не нужен.
# Перед публикацией укажи настоящий AdMob App ID:
# android.meta_data = com.google.android.gms.ads.APPLICATION_ID=ca-app-pub-XXXXXXXXXXXXXXXX~YYYYYYYYYY


# ---------- Опционально ----------

# Иконка приложения — раскомментируй, если положишь icon.png в проект:
# icon.filename = %(source.dir)s/icon.png

# Заставка перед запуском — раскомментируй, если положишь presplash.png:
# presplash.filename = %(source.dir)s/presplash.png


[buildozer]

# 2 — подробный вывод, полезен при ошибках
log_level = 2

# Предупреждать, если Buildozer запущен с sudo/root
warn_on_root = 1
