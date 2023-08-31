#!/bin/bash
PORT=1025
INBOX_PATH=inbox

# set up configuration
if [ -f "conf.txt" ]; then
    rm conf.txt
fi
if [ -d "$INBOX_PATH" ]; then
    rm -rf $INBOX_PATH
fi
coverage erase
echo "server_port=$PORT" >> conf.txt
echo "inbox_path=$INBOX_PATH" >> conf.txt
mkdir $INBOX_PATH
# start testing
fuser -k $PORT/tcp

for tc in e2e_tests/*.in; do
    [ -e "$tc" ] || continue
    ( (trap "echo Got SigInt" SIGINT; nohup coverage run -a server.py conf.txt > server.log) & ) &
    sleep 1
    (while IFS= read -r line || [ -n "$line" ];
    do
    echo $line;
    sleep 0.1
    done < $tc) | ./netcat 127.0.0.1 $PORT
    sleep 1
    tc_out=$(echo "$tc" | sed 's/.in/.out/')
    tc_actual_out=$(echo "$tc" | sed 's/.in/.actual.out/')
    cp -nf server.log $tc_actual_out
    char_count=$(diff $tc_actual_out $tc_out | wc -c)
    if [ $char_count -eq 0 ]
    then
        echo -e "\033[1mTestcase $tc passed!\033[0m"
    else
        echo -e "\033[1mDid not pass testcase $tc\033[0m"
    fi
    kill -INT $(pgrep -fl server.py | cut -f1 -d ' ')
done
rm server.log
coverage report --show-missing