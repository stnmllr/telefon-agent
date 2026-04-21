@echo off
echo ========================================
echo ERP Dokumentation Upload nach GCS
echo Gesamtgroesse: ~500 MB (geschaetzt)
echo ========================================
echo.

set BUCKET=gs://boxwood-mantra-489408-c0-handbuecher
set DOKU=M:\doku

echo [1/10] eevolution...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\eevolution" %BUCKET%/erp/eevolution/
echo.

echo [2/10] auftrag...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\auftrag" %BUCKET%/erp/auftrag/
echo.

echo [3/10] artikel...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\artikel" %BUCKET%/erp/artikel/
echo.

echo [4/10] schnittstellen...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\schnittstellen" %BUCKET%/erp/schnittstellen/
echo.

echo [5/10] einkauf...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\einkauf" %BUCKET%/erp/einkauf/
echo.

echo [6/10] kulimi...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\kulimi" %BUCKET%/erp/kulimi/
echo.

echo [7/10] chargen...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\chargen" %BUCKET%/erp/chargen/
echo.

echo [8/10] inventur...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\inventur" %BUCKET%/erp/inventur/
echo.

echo [9/10] preiskon...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\preiskon" %BUCKET%/erp/preiskon/
echo.

echo [10/10] ProFi (FIBU)...
gsutil -m rsync -r -x ".*[Aa]rchiv.*" "%DOKU%\ProFi" %BUCKET%/fibu/
echo.

echo ========================================
echo Upload abgeschlossen!
echo Pruefen mit:
echo gsutil ls %BUCKET%/erp/
echo ========================================
pause
