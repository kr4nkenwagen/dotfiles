# Sourced by lib.sh and sway-menu.
# k4b64v VAR STRING: base64 into VAR without a fork (a menu prints a row per app, file or
# network: two base64 processes a row cost ~3 ms, this ~0.4); for short strings, k4b64 for data
_K4B64=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/
k4b64v() {
  local LC_ALL=C _k4s=$2 _k4o="" _k4i _k4n _k4a _k4b _k4c _k4v; _k4n=${#_k4s}
  for (( _k4i = 0; _k4i + 2 < _k4n; _k4i += 3 )); do
    printf -v _k4a '%d' "'${_k4s:_k4i:1}"; printf -v _k4b '%d' "'${_k4s:_k4i+1:1}"; printf -v _k4c '%d' "'${_k4s:_k4i+2:1}"
    (( _k4v = (_k4a & 255) << 16 | (_k4b & 255) << 8 | (_k4c & 255) ))
    _k4o+=${_K4B64:_k4v>>18&63:1}${_K4B64:_k4v>>12&63:1}${_K4B64:_k4v>>6&63:1}${_K4B64:_k4v&63:1}
  done
  if (( _k4n - _k4i == 1 )); then printf -v _k4a '%d' "'${_k4s:_k4i:1}"; (( _k4v = (_k4a & 255) << 16 ))
    _k4o+=${_K4B64:_k4v>>18&63:1}${_K4B64:_k4v>>12&63:1}==
  elif (( _k4n - _k4i == 2 )); then printf -v _k4a '%d' "'${_k4s:_k4i:1}"; printf -v _k4b '%d' "'${_k4s:_k4i+1:1}"
    (( _k4v = (_k4a & 255) << 16 | (_k4b & 255) << 8 )); _k4o+=${_K4B64:_k4v>>18&63:1}${_K4B64:_k4v>>12&63:1}${_K4B64:_k4v>>6&63:1}=; fi
  printf -v "$1" '%s' "$_k4o"; }
