#!/bin/bash
cd /i/AG/air-wudhu
PY=/i/AG/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
i=0
while IFS='|' read -r topik sudut; do
  i=$((i+1))
  echo "=== [$i] $topik ($(date +%H:%M:%S))"
  if [ -n "$sudut" ]; then
    $PY aw_main.py auto --topik "$topik" --sudut "$sudut"
  else
    $PY aw_main.py auto --topik "$topik"
  fi
  echo "=== selesai [$i] exit=$? ($(date +%H:%M:%S))"
done <<'LIST'
Mengapa kita harus wudhu sebelum sholat|
Laki-laki mengapa harus sholat di masjid|Sampaikan sesuai sumber, jelaskan hukumnya dan perbedaan pendapat ulama bila ada, dengan bahasa santun dan tidak menghakimi
Mengapa istri harus patuh sama suami|Sampaikan sesuai sumber dengan bahasa santun dan seimbang: sebutkan batasan ketaatan dan hak istri juga
LIST
echo "ALL_DONE $(date +%H:%M:%S)"
