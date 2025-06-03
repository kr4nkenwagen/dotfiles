#!/bin/fish
copyq select $(copyq eval -- "tab('clipboard'); for(i=0; i<size(); ++i) print(i +  '| ' + str(read(i)).replace('\n', ' ') + '\n');" | dmenu -b -l 10 -i | cut -d '|' -f 1)
