# IMPORTANT: sirf 1 worker (-w 1). Scheduler app ke andar hi chalta hai —
# 2 workers matlab 2 scheduler matlab har video 2 baar upload. Threads badha sakte ho.
web: gunicorn app:app -w 1 --threads 8 -b 0.0.0.0:$PORT --timeout 1800
