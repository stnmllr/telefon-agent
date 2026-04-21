@echo off
echo ========================================
echo ERP Dokumentation Upload nach GCS
echo ========================================
echo.

set BUCKET=gs://boxwood-mantra-489408-c0-handbuecher
set DOKU=M:\doku

echo [1/10] eevolution...
gcloud storage rsync -r "%DOKU%\eevolution" %BUCKET%/erp/eevolution/ --exclude=".*[Aa]rchiv.*"
echo Fertig: eevolution
echo.

echo [2/10] auftrag...
gcloud storage rsync -r "%DOKU%\auftrag" %BUCKET%/erp/auftrag/ --exclude=".*[Aa]rchiv.*"
echo Fertig: auftrag
echo.

echo [3/10] artikel...
gcloud storage rsync -r "%DOKU%\artikel" %BUCKET%/erp/artikel/ --exclude=".*[Aa]rchiv.*"
echo Fertig: artikel
echo.

echo [4/10] schnittstellen...
gcloud storage rsync -r "%DOKU%\schnittstellen" %BUCKET%/erp/schnittstellen/ --exclude=".*[Aa]rchiv.*"
echo Fertig: schnittstellen
echo.

echo [5/10] einkauf...
gcloud storage rsync -r "%DOKU%\einkauf" %BUCKET%/erp/einkauf/ --exclude=".*[Aa]rchiv.*"
echo Fertig: einkauf
echo.

echo [6/10] kulimi...
gcloud storage rsync -r "%DOKU%\kulimi" %BUCKET%/erp/kulimi/ --exclude=".*[Aa]rchiv.*"
echo Fertig: kulimi
echo.

echo [7/10] chargen...
gcloud storage rsync -r "%DOKU%\chargen" %BUCKET%/erp/chargen/ --exclude=".*[Aa]rchiv.*"
echo Fertig: chargen
echo.

echo [8/10] inventur...
gcloud storage rsync -r "%DOKU%\inventur" %BUCKET%/erp/inventur/ --exclude=".*[Aa]rchiv.*"
echo Fertig: inventur
echo.

echo [9/10] preiskon...
gcloud storage rsync -r "%DOKU%\preiskon" %BUCKET%/erp/preiskon/ --exclude=".*[Aa]rchiv.*"
echo Fertig: preiskon
echo.

echo [10/10] ProFi (FIBU)...
gcloud storage rsync -r "%DOKU%\ProFi" %BUCKET%/fibu/ --exclude=".*[Aa]rchiv.*"
echo Fertig: ProFi
echo.

echo ========================================
echo Upload abgeschlossen!
echo ========================================
gcloud storage ls %BUCKET%/erp/
gcloud storage ls %BUCKET%/fibu/
echo ========================================
pause
