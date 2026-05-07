#!/bin/bash
# radio.sh — lightweight internet radio player via mpv
# Useful for testing GLava visualizer without a browser or full music player.
# Requires: mpv

MODEL=$(hostnamectl 2>/dev/null | grep "Hardware Model" | cut -d ':' -f2 | xargs)
if [ -z "$MODEL" ]; then
    MODEL=$(cat /sys/class/dmi/id/product_name 2>/dev/null || echo "unknown")
fi

while true; do
    clear
    echo "=========================================="
    echo "   RADIO ON: $MODEL"
    echo "=========================================="
    echo " --- Polish stations (may be geo-blocked) ---"
    echo " 1) Jedynka             5) RMF FM (server 1)"
    echo " 2) Dwójka              6) RMF FM (server 2)"
    echo " 3) Trójka              7) Radio Zet"
    echo " 4) Czwórka             8) DJ Party"
    echo ""
    echo " --- International (SomaFM — no geo-block) ---"
    echo " 9) Groove Salad        (ambient / downtempo)"
    echo "10) Drone Zone          (atmospheric / minimal)"
    echo "11) Secret Agent        (lounge / jazz / spy)"
    echo "12) Underground 80s     (synthpop / new wave)"
    echo "13) DEF CON Radio       (hacking music / electronic)"
    echo "14) Beat Blender        (deep house / chill)"
    echo "------------------------------------------"
    echo " q) Quit"
    echo "=========================================="
    read -rp "Choose station (1-14): " choice
    case $choice in
        1)  mpv --no-video http://mp3.polskieradio.pl:8900/ ;;
        2)  mpv --no-video "http://stream3.polskieradio.pl:8952/;.mp3" ;;
        3)  mpv --no-video http://41.dktr.pl:8000/trojka.ogg ;;
        4)  mpv --no-video "http://stream3.polskieradio.pl:8906/;stream" ;;
        5)  mpv --no-video http://195.150.20.242:8000/rmf_fm ;;
        6)  mpv --no-video http://31.192.216.8/rmf_fm ;;
        7)  mpv --no-video "https://zt03.cdn.eurozet.pl/zet-old.mp3?redirected=03" ;;
        8)  mpv --no-video http://djmixes.radioparty.pl:8035/ ;;
        9)  mpv --no-video https://ice.somafm.com/groovesalad ;;
        10) mpv --no-video https://ice.somafm.com/dronezone ;;
        11) mpv --no-video https://ice.somafm.com/secretagent ;;
        12) mpv --no-video https://ice.somafm.com/u80s ;;
        13) mpv --no-video https://ice.somafm.com/defcon ;;
        14) mpv --no-video https://ice.somafm.com/beatblender ;;
        q)  echo "Closing..."; exit 0 ;;
        *)  echo "Invalid option."; sleep 1 ;;
    esac
done
