#!/bin/bash
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSV_PATH="$BASE_DIR/radios.csv"
CONF_PATH="$BASE_DIR/bose.conf"
PIPE_PATH="$BASE_DIR/radio_pipe"
IPC_SOCKET="/tmp/mpvsocket"

get_bose_mac() {
    if [ -f "$CONF_PATH" ]; then
        echo $(grep "MAC=" "$CONF_PATH" | cut -d'=' -f2)
    else
        echo ""
    fi
}

propagate_metadata() {
    local radio_name="$1"
    local last_title=""
    
    bluetoothctl media.player.track.title "$radio_name" > /dev/null 2>&1
    bluetoothctl media.player.track.artist "Radiolink" > /dev/null 2>&1

    while [ -S "$IPC_SOCKET" ]; do
        sleep 3
        if [ -S "$IPC_SOCKET" ]; then
            current=$(echo '{"command": ["get_property", "media-title"]}' | socat - "$IPC_SOCKET" 2>/dev/null | jq -r '.data' 2>/dev/null)
            
            if [ -n "$current" ] && [ "$current" != "null" ] && [ "$current" != "$last_title" ]; then
                last_title="$current"
                bluetoothctl media.player.track.title "$current" > /dev/null 2>&1
                bluetoothctl media.player.track.artist "$radio_name" > /dev/null 2>&1
            fi
        fi
    done
}

play_radio() {
    local radio_name="$1"
    local radio_url="$2"
    BOSE_MAC=$(get_bose_mac)
    if [ -z "$BOSE_MAC" ]; then return; fi
    
    pkill -9 mpv
    rm -f $IPC_SOCKET
    sleep 0.1
    
    DEVICE="alsa/bluealsa:DEV=$BOSE_MAC"
    
    mpv --ao=alsa --audio-device=$DEVICE --input-ipc-server=$IPC_SOCKET --stream-buffer-size=512KiB "$radio_url" > /dev/null 2>&1 &
    
    (
        for i in {1..10}; do
            if [ -S "$IPC_SOCKET" ]; then
                propagate_metadata "$radio_name"
                break
            fi
            sleep 0.5
        done
    ) &
}

slugify() {
    echo "$1" | iconv -f utf-8 -t ascii//TRANSLIT | tr -cd '[:alnum:]' | tr '[:upper:]' '[:lower:]'
}

[ -p "$PIPE_PATH" ] || mkfifo "$PIPE_PATH"

while true; do
    if read line < "$PIPE_PATH"; then
        BOSE_MAC=$(get_bose_mac)
        
        case "$line" in
            "start") 
                if [ -n "$BOSE_MAC" ]; then bluetoothctl connect "$BOSE_MAC"; fi
                ;;
            "stop")  
                pkill -9 mpv
                rm -f $IPC_SOCKET
                if [ -n "$BOSE_MAC" ]; then bluetoothctl disconnect "$BOSE_MAC"; fi
                ;;
            "vol_up")
                [ -S "$IPC_SOCKET" ] && echo '{"command": ["cycle", "volume", "up"]}' | socat - "$IPC_SOCKET" > /dev/null 2>&1
                ;;
            "vol_down")
                [ -S "$IPC_SOCKET" ] && echo '{"command": ["cycle", "volume", "down"]}' | socat - "$IPC_SOCKET" > /dev/null 2>&1
                ;;
            "vol_mute")
                [ -S "$IPC_SOCKET" ] && echo '{"command": ["set_property", "mute", false]}' | socat - "$IPC_SOCKET" > /dev/null 2>&1
                ;;
            "vol_unmute")
                [ -S "$IPC_SOCKET" ] && echo '{"command": ["set_property", "mute", true]}' | socat - "$IPC_SOCKET" > /dev/null 2>&1
                ;;
            "sys_poweroff")
                pkill -9 mpv
                rm -f $IPC_SOCKET
                if [ -n "$BOSE_MAC" ]; then bluetoothctl disconnect "$BOSE_MAC"; fi
                sleep 0.5
                sudo /usr/sbin/poweroff
                ;;
            *)
                if [ -f "$CSV_PATH" ]; then
                    while IFS=, read -r name url cat; do
                        clean_name=$(echo "$name" | tr -d '"\r')
                        clean_url=$(echo "$url" | tr -d '"\r ')
                        slug=$(slugify "$clean_name")
                        
                        if [ -n "$slug" ] && [ "$slug" = "$line" ]; then
                            play_radio "$clean_name" "$clean_url"
                            break
                        fi
                    done < "$CSV_PATH"
                fi
                ;;
        esac
    fi
done
