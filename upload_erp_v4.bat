@echo off
echo ========================================
echo ERP Dokumentation Upload nach GCS
echo ========================================

set BUCKET=gs://boxwood-mantra-489408-c0-handbuecher
set DOKU=M:\doku

echo [1/10] eevolution...
gsutil -m cp -r "%DOKU%\eevolution\*" %BUCKET%/erp/eevolution/
echo Fertig: eevolution

echo [2/10] auftrag...
gsutil -m cp -r "%DOKU%\auftrag\*" %BUCKET%/erp/auftrag/
echo Fertig: auftrag

echo [3/10] artikel...
gsutil -m cp -r "%DOKU%\artikel\*" %BUCKET%/erp/artikel/
echo Fertig: artikel

echo [4/10] schnittstellen...
gsutil -m cp -r "%DOKU%\schnittstellen\*" %BUCKET%/erp/schnittstellen/
echo Fertig: schnittstellen

echo [5/10] einkauf...
gsutil -m cp -r "%DOKU%\einkauf\*" %BUCKET%/erp/einkauf/
echo Fertig: einkauf

echo [6/10] kulimi...
gsutil -m cp -r "%DOKU%\kulimi\*" %BUCKET%/erp/kulimi/
echo Fertig: kulimi

echo [7/10] chargen...
gsutil -m cp -r "%DOKU%\chargen\*" %BUCKET%/erp/chargen/
echo Fertig: chargen

echo [8/10] inventur...
gsutil -m cp -r "%DOKU%\inventur\*" %BUCKET%/erp/inventur/
echo Fertig: inventur

echo [9/10] preiskon...
gsutil -m cp -r "%DOKU%\preiskon\*" %BUCKET%/erp/preiskon/
echo Fertig: preiskon

echo [10/10] ProFi (FIBU)...
gsutil -m cp -r "%DOKU%\ProFi\*" %BUCKET%/fibu/
echo Fertig: ProFi

echo ========================================
echo Upload abgeschlossen!
echo ========================================
pause