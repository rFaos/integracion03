@echo off
REM Compila y ejecuta Library Desktop (requiere JDK 17+; JavaFX en .\lib)
cd /d "%~dp0"
if not exist lib\javafx-web-21.0.5-win.jar (
  echo Descargando JavaFX 21.0.5 desde Maven Central...
  mkdir lib 2>nul
  for %%m in (base graphics controls web media) do curl -sfL -o lib\javafx-%%m-21.0.5-win.jar https://repo1.maven.org/maven2/org/openjfx/javafx-%%m/21.0.5/javafx-%%m-21.0.5-win.jar
)
if exist out rmdir /s /q out
mkdir out
dir /s /b src\main\java\*.java > sources.txt
javac -encoding UTF-8 --module-path lib --add-modules javafx.controls,javafx.web -d out @sources.txt || exit /b 1
del sources.txt
copy /y src\main\resources\* out\ >nul
java --module-path lib --add-modules javafx.controls,javafx.web -cp out mx.udem.library.Main
