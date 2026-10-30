#!/bin/bash
export HOME=/tmp/etest-home
xvfb-run -a /tmp/claude-0/-home-claude-doodlecompanion/2564a2b0-0bec-5719-a8ed-d567cad8c3dc/scratchpad/etest/node_modules/electron/dist/electron --no-sandbox /tmp/claude-0/-home-claude-doodlecompanion/2564a2b0-0bec-5719-a8ed-d567cad8c3dc/scratchpad/ds3d/build/app > /tmp/etest-home/electron.log 2>&1 &
EPID=$!
for i in $(seq 1 40); do sleep 1; curl -s -m 2 -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_state","arguments":{}}}' > /tmp/etest-home/state.json && grep -q values /tmp/etest-home/state.json && break; done
head -c 400 /tmp/etest-home/state.json; echo
curl -s -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"set_values","arguments":{"values":{"armL":60},"key":true}}}' | head -c 200; echo
call() { curl -s -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d "{\"jsonrpc\":\"2.0\",\"id\":9,\"method\":\"tools/call\",\"params\":{\"name\":\"$1\",\"arguments\":$2}}" | head -c ${3:-300}; echo; }
call set_shot '{"scene":"Smoke Scene"}' 120
call add_shot '{"duplicate":false}' 200
call move_shot '{"shot":"sh020","to":0}' 200
call carousel '{"action":"snap","shot":"sh010","frame":5}' 300
call carousel '{"action":"bubble","slide":0,"bubble":{"text":"Hi"}}' 300
call apply_camera_preset '{"list":true}' 150
call add_marker '{"frame":10,"note":"beat"}' 200
call save_version '{"label":"smoke"}' 200
call storyboard '{}' 200
call set_shot_look '{"horizonLock":true,"ink":120}' 200
call anim_tool '{"action":"loop_check"}' 200
call anim_tool '{"action":"onion","on":true}' 200
call story '{"action":"retention"}' 200
call set_character '{"character":"koala"}' 200
call library_list '{"category":"motion","query":"wave","limit":2}' 300
call library_use '{"id":"motion-wave-hello","frame":0}' 200
call library_use '{"id":"prop-letter_envelope","hold":"R"}' 200
call set_stage '{"stage":{"set":"bedroom","outfit":"raincoat"}}' 300
curl -s -o /dev/null -w "library preview: %{http_code}\n" "http://127.0.0.1:54190/lib/previews/outfit/outfit-raincoat.png"
curl -s -o /dev/null -w "library json blocked: %{http_code}\n" "http://127.0.0.1:54190/lib/library.json"
call production '{"action":"change_log"}' 300
call workflow '{"action":"rules","frame":0}' 200
call workflow '{"action":"status","status":"polish"}' 200
call production '{"action":"health"}' 300
call production '{"action":"preflight"}' 200
call anim2 '{"action":"ik","limb":"armR","offset":[0,-0.03,0.05]}' 200
call anim2 '{"action":"balance"}' 200
call anim2 '{"action":"path","what":"armR"}' 200
call story2 '{"action":"beat_map"}' 200
call story2 '{"action":"genre","genre":"comedy","frame":5}' 200
curl -s -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d '[{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}},{"jsonrpc":"2.0","id":2,"method":"tools/list"}]' | python3 -c "import json,sys;j=json.load(sys.stdin);print('update safety probe:', bool(j[0]['result']['serverInfo']) and len(j[1]['result']['tools'])>10)"
curl -s -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":4,"method":"tools/list"}' | python3 -c "import json,sys;print([t['name'] for t in json.load(sys.stdin)['result']['tools']])"
curl -s -X POST http://127.0.0.1:54190/mcp -H 'content-type: application/json' -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"save","arguments":{}}}' | head -c 300; echo
curl -s -o /dev/null -w "evil origin: %{http_code}\n" -X POST http://127.0.0.1:54190/mcp -H 'origin: https://evil.example' -H 'content-type: application/json' -d '{}'
kill $EPID; sleep 1; python3 /tmp/claude-0/-home-claude-doodlecompanion/2564a2b0-0bec-5719-a8ed-d567cad8c3dc/scratchpad/killmatch.py "electron --no-sandbox"
grep -iv "dbus\|gpu\|libva\|viz\|vaapi\|ozone\|ERROR:bus" /tmp/etest-home/electron.log | head -20
find /tmp/etest-home/Documents -type f | head
