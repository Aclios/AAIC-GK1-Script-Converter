import struct
import os
import json
import sys
import traceback
import io

def readuint(f):
    return struct.unpack('<I',f.read(4))[0]

def writeuint(f,value):
    f.write(struct.pack('<I',value))

with open('code_info.json') as f:
    CODE_DICT = json.load(f)

REVERSE_CODE_DICT = {v[0]:k for k,v in CODE_DICT.items()}

class GK1Script:
    def __init__(self,filepath):
        with open(filepath,mode='rb') as f:
            self.entry_count = readuint(f)
            self.entry_header_list = [GK1EntryInfo(f) for _ in range(self.entry_count)]
            self.entry_data_list = [self.read_entry(f,header.read_count) for header in self.entry_header_list]

    def read_entry(self,f,read_count):
        output_data = ""
        current_count = 0
        while current_count < read_count:
            data = readuint(f)

            if data == 0xa:
                output_data += '<NextLine>\n'

            elif data == 0xffffff: #code flag

                current_count += 1
                code_id = hex(readuint(f))

                if code_id not in CODE_DICT:
                    raise Exception(f"Missing code: {code_id} ; offset:{hex(f.tell() - 4)}")

                code_string, arg_count = CODE_DICT[code_id]
                if arg_count == 0:
                    output_data += f'<{code_string}>'
                else:
                    arg_list = [str(readuint(f)) for _ in range(arg_count)]
                    output_data += f'<{code_string}:{",".join(arg_list)}>'
                    current_count += arg_count

            else:
                output_data += chr(data)

            current_count += 1

        return output_data


    def write_to_txt(self,filepath):
        with open(filepath,mode='x',encoding='utf-8') as f:
            for idx, header in enumerate(self.entry_header_list):
                f.write(f'[{header.id1},{header.id2},{header.some_offset}]\n\n')
                f.write(self.entry_data_list[idx])
                f.write('\n\n')


class GK1EntryInfo:
    def __init__(self,f):
        self.id1 = readuint(f)
        self.id2 = readuint(f)
        self.some_offset = readuint(f)
        self.read_count = readuint(f) #number of times you need to read 4 bytes


class TXT:
    def __init__(self,filepath):
        self.entries = []
        if filepath.endswith('.txt'):
            with open(filepath,mode='r',encoding='utf-8') as f:
                char = f.read(1)
                while char not in ["[",""]:
                    char = f.read(1)
                if char == "": #supporting blank files
                    return
                while True:
                    entry = TXTEntry()
                    entry.id1, entry.id2, entry.some_offset = self.readtxtentryheader(f)
                    entry.data, flag = self.readtxtentry(f)
                    self.entries.append(entry)
                    if flag:
                        break
                for entry in self.entries:
                    entry.byte_data = entry.data_to_bytes()
                    entry.read_count = len(entry.byte_data) // 4

    def readtxtentryheader(self,f):
        data = ""
        char = f.read(1)
        while char != ']':
            data += char
            char = f.read(1)
        id1, id2, some_offset = data.split(',')
        return int(id1), int(id2), int(some_offset)

    def readtxtentry(self,f):
        entry_data = ""
        char = f.read(1)
        while char not in ["[",""]:
            if char not in ["\n","\r"]:
                entry_data += char
            char = f.read(1)
        return entry_data, char == ""

    def write_to_GK1Script(self,filepath):
        with open(filepath,mode='wb') as f:
            writeuint(f,len(self.entries))
            for entry in self.entries:
                writeuint(f,entry.id1)
                writeuint(f,entry.id2)
                writeuint(f,entry.some_offset)
                writeuint(f,entry.read_count)
            for entry in self.entries:
                f.write(entry.byte_data)

class TXTEntry:
    def __init__(self):
        self.id1 = self.id2 = 0
        self.some_offset = 0
        self.read_count = 0
        self.data = ""

    def data_to_bytes(self):
        idx = 0
        byte_data = bytearray()
        f = io.StringIO(self.data)
        char = f.read(1)
        while char != '':
            if char == '<':
                char = f.read(1)
                code = ""
                while char != '>':
                    code += char
                    char = f.read(1)
                byte_data += self.parse_code(code)
            else:
                byte_data += ord(char).to_bytes(4,'little')
            char = f.read(1)
        return byte_data

    def parse_code(self,code_data):
        CODE_FLAG = 0xffffff
        parse = code_data.split(":")
        code = parse[0]
        if len(parse) == 1:
            if code == 'NextLine':
                return ord('\n').to_bytes(4,'little')
            else:
                str_code = REVERSE_CODE_DICT[code]
                return CODE_FLAG.to_bytes(4,'little') + int(str_code,16).to_bytes(4,'little')
        else:
            byte_data = bytearray()
            byte_data += CODE_FLAG.to_bytes(4,'little')
            str_code = REVERSE_CODE_DICT[code]
            byte_data += int(str_code,16).to_bytes(4,'little')
            args = parse[1].split(',')
            for arg in args:
                byte_data += int(arg).to_bytes(4,'little')
            return byte_data


def batch_GK1Script_to_txt(input_dir,output_dir):
    for file in os.listdir(input_dir):
        if file.endswith('.bytes'):
            print(f"Exporting {file}...")
            script = GK1Script(os.path.join(input_dir,file))
            script.write_to_txt(os.path.join(output_dir,file+'.txt'))

def batch_txt_to_GK1Script(input_dir,output_dir):
    for file in os.listdir(input_dir):
        if not file.endswith('.txt'):
            continue
        try:
            print(f"Converting {file} to GK1 Script...")
            txt = TXT(os.path.join(input_dir,file))
            txt.write_to_GK1Script(os.path.join(output_dir,file[:-4]))
        except:
            print(f"Error while converting {file}:")
            print(traceback.format_exc())

def main():
    args = sys.argv
    if len(sys.argv) != 4:
        print('Usage: "py AAIC_SPT_converter.py [-spt] [-txt] <input_dir> <output_dir>"')
        return
    if sys.argv[1] == '-spt':
        batch_GK1Script_to_txt(sys.argv[2],sys.argv[3])
    elif sys.argv[1] == '-txt':
        batch_txt_to_GK1Script(sys.argv[2],sys.argv[3])
    else:
        print("Use the -spt option to convert spt to txt, or the -txt option to convert txt to spt.")

if __name__ == '__main__':
    main()