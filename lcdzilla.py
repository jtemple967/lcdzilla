import math
from lcd.lcd import LCD, LCD_BACKLIGHT, LCD_NOBACKLIGHT
from lcd.i2c_pcf8574_interface import I2CPCF8574Interface
from lcd.lcd import CursorMode
import busio
import board

class lcdzilla:

    LCD_PFC8574 = 1
    LCD_HD44789 = 2
    SCROLL_DOWN = 1
    SCROLL_UP = -1

    def __init__(self, display_type, addr, scl_pin, sda_pin, num_lines=4, num_characters=20):

        self._display_type = display_type
        self._addr = addr
        self._num_lines = num_lines
        self._num_characters = num_characters
        self._first_visible_line = None
        self._last_visible_line = None
        self._screen_def = None
        self._alpha_lower_characters = ""
        self._alpha_upper_characters = ""
        self._symbol_characters = ""
        self._numbers = ""
        self._cur_character_set = None
        self._char_set_key = ""
        self._bkspc_key = ""
        self._cursor_positions = None
        self._cur_row = -1
        self._cur_field = -1
        self._edit_mode = False
        self._edit_numbers = False
        self._edit_pos = 0
        self._edit_item = []
        self._scl_pin = scl_pin
        self._sda_pin = sda_pin
        self._debug = False
        self._char_set_key_label = ""
        self._first_visible_row = -1
        self._last_visible_row = -1


        try:
            # Here we will build an interface for the supported display
            self._i2c = busio.I2C(self._scl_pin, self._sda_pin)
            if self._display_type == self.LCD_PFC8574:
                self._lcd = LCD(I2CPCF8574Interface(self._i2c, self._addr),
                                num_rows=self._num_lines, num_cols=self._num_characters)
        except Exception as e:
            raise Exception("Error trying to create connection to LCD: {0}".format(e))
        
        # Clear the LCD and hide the cursor
        self._lcd.set_cursor_mode(CursorMode.HIDE)
        self._lcd.clear()
        
    def set_debug(self, debug_value):
        self._debug = debug_value
        
    def set_alpha_lower(self, alpha_lower_characters):
        self._alpha_lower_characters = alpha_lower_characters

    def set_alpha_upper(self, alpha_upper_characters):
        self._alpha_upper_characters = alpha_upper_characters
        
    def set_symbols(self, symbol_characters):
        self._symbol_characters = symbol_characters

    def set_numbers(self, numbers):
        self._numbers = numbers

    def set_character_set_key(self, key):
        self._char_set_key = key
        
    def set_bkspc_key(self, key):
        self._bkspc_key = key
        
    def get_cursor_position(self):
        return [self._cur_row, self._cur_field]

    def set_cursor_position(self, cursor_position):
        self._cur_row = cursor_position[0]
        self._cursor_positions = cursor_position[1]

    def load_screen(self, screen_def, offset=0):

        self._screen_def = screen_def

        # Clear the display
        self._lcd.clear()
        self._char_set_key_label = ""
        self._first_visible_row = -1
        self._last_visible_row = -1
        
        # Hide the cursor
        self._lcd.set_cursor_mode(CursorMode.HIDE)
        
        # Reset cursor row/field
        self._cur_row = -1
        self._cur_field = -1
        # Reset the field that will keep track of the row/columns where the cursor can appear
        self._cursor_positions = []

        # Loop through the array elements.  The outer element defines one line on the lcd.
        # Each line has one or more array elements which represent subfields of a single line
        lcd_text = ""
        self._edit_mode = False
        self._selectable = False
        self._edit_numbers = False
        self._edit_pos = 0
        self._edit_item = []
        self._cur_character_set = None
        lcd_line = ""
        for line_idx, line in enumerate(screen_def):
            if line_idx >= offset:
                # Set the first visible row
                if self._first_visible_row < 0:
                    self._first_visible_row = line_idx
                lcd_line = ""
                cursor_positions = []
                # How many subfields? Should we have a maximum?
                num_subfields = len(line)
                # Determine the length of each subfield in the line
                subfield_len = math.floor(self._num_characters / num_subfields)
                if subfield_len < self._num_characters:
                    subfield_len += 1
                for subfield_idx, subfield in enumerate(line):
                    # Is this field selectable?
                    if "select" in subfield and subfield["select"] is True:
                        self._selectable = True
                        cursor_positions.append(len(lcd_line))
                        # Use the first selectable field as the cursor default
                        if self._cur_row == -1:
                            self._cur_row = (line_idx-offset)
                            self._cur_field = subfield_idx
                    # text element is required
                    if "text" not in subfield:
                        raise Exception("'text' element missing from definition")
                    # this is edit mode?
                    if "edit" in subfield and subfield["edit"] is True:
                        self._edit_mode = True
                        if "type" in subfield:
                            self._edit_numbers = (subfield["type"] == "number")
                        else:
                            self._edit_numbers = False
                        # Set the initial character set to use
                        self._set_character_set(subfield["text"], 0)
                        # Store the line and subfield being edited
                        self._edit_item = [line_idx, subfield_idx]
                    # Only write to the LCD if we haven't filled it up yet
                    if line_idx < (self._num_lines+offset):
                        self._last_visible_row = line_idx
                        # Construct the line to write to the LCD
                        if type(subfield['text']) == int:
                            text = str(subfield['text'])
                        else:
                            text = subfield['text']
                        lcd_line += ("{0:" + str(subfield_len) + "." + str(subfield_len) + "}").format(text)
                if line_idx < (self._num_lines+offset):
                    # The line cannot be longer than the number of characters defined.
                    lcd_line = ("{0: " + str(self._num_characters) + "." + str(self._num_characters) + "}").format(lcd_line)
                    lcd_text += lcd_line
                self._cursor_positions.append(cursor_positions)

        # If a field is selectable but no default throw an error
        if self._selectable and self._cur_row < 0:
            raise Exception("Selectable fields in screen definition but no default specified")
        
        # If debugging print cursor positions
        if self._debug:
            print(self._cur_row)
            print(self._cur_field)
            print(self._cursor_positions)
            
        # Send to screen
        self._lcd.print(lcd_text)
        
        # Set the status line to switch character sets when not editing a number
        status_text = ""
        if self._edit_mode:
            if not self._edit_numbers:
                self.load_status_line(self._char_set_key_label + self._bkspc_key + "=Bkspc", line_number=(self._num_lines-2))
            self.load_status_line("Ent=Save")
        
        # If the there is a selectable field then display the cursor.
        if self._selectable:
            if self._debug:
                print("Setting cursor position: {0}, {1}".format(self._cur_row, self._cur_field))
            cursor_pos = self._cursor_positions[self._cur_row][self._cur_field]
            self._lcd.set_cursor_pos(self._cur_row, cursor_pos)
            self._lcd.set_cursor_mode(CursorMode.BLINK)

    def load_status_line(self, status_text, line_number=None):
        
        if self._debug:
            print("Updating status line: {0}".format(status_text))
        if not line_number:
            line_number = (self._num_lines-1)
        # Make sure the status text doesn't exceed the width of the lcd
        if len(status_text) > self._num_characters:
            status_text = status_text[:self._num_characters]
        # Position to the line being updated
        self._lcd.set_cursor_pos(line_number, 0)
        # Center the text and show
        self._lcd.print(status_text.center(self._num_characters))
        
    def cursor_down(self):
        # If we're in edit mode then cursor down will change the character at the cursor to
        # the next element in the array
        if self._edit_mode:
            # Get the subfield definition being edited
            edit_subfield = self._screen_def[self._edit_item[0]][self._edit_item[1]]
            if self._debug:
                print("Subfield being edited: {0}".format(edit_subfield))
            # Get the current cursor position
            save_cursor = self._lcd.cursor_pos()
            # Get the edit text
            edit_value = edit_subfield['text']
            if self._debug:
                print("Value being edited: {0}".format(edit_value))
            # Get the character from the text element that we're currently on
            if not self._edit_numbers:
                if self._edit_pos > (len(edit_value)-1):
                    cur_char = ""
                else:
                    cur_char = edit_value[self._edit_pos]
                if self._debug:
                    print("Finding character {0}".format(cur_char))
                char_index = self._cur_character_set.find(cur_char)
                if self._debug:
                    print("Character index: {0}".format(char_index))
                if char_index >= 0:
                    if char_index < (len(self._cur_character_set)-1):
                        cur_char = self._cur_character_set[char_index+1]
                    else:
                        cur_char = self._cur_character_set[0]
                else:
                    cur_char = self._cur_character_set[0]
                # Update the character in the edit value with the new value
                edit_value = edit_value[:self._edit_pos] + cur_char + edit_value[self._edit_pos+1:]
            # Else for a number just increment by 1 unless it reaches the set maximum value
            else:
                if 'min_value' in edit_subfield:
                    if (edit_value-1) >= edit_subfield['min_value']:
                        edit_value -= 1
                else:
                    edit_value -= 1
            # Replace the text with the new value
            edit_subfield["text"] = edit_value
            # If editing numbers replace the entire line
            if self._edit_numbers:
                lcd_line = ("{0:" + str(self._num_characters) + "." + str(self._num_characters) + "}").format(str(edit_value))
                self._lcd.print(lcd_line)
            else:
                self._lcd.print(cur_char)
            # Reset the cursor position
            self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
            if self._debug:
                print("Cursor position: {0}".format(self._edit_pos))
        else:
            
            # If the new current row is greater than the last visible row and
            # the last visible row is less than the number of rows then reload
            # the screen with the appropriate offset
            if self._debug:
                print("Current row: {0}; Last visible row: {1}".format(self._cur_row, self._last_visible_row))
            if (self._cur_row+1+self._first_visible_row) > self._last_visible_row and (len(self._screen_def)-1) > self._last_visible_row:
                self.load_screen(self._screen_def, self._first_visible_row+1)
            else:
                # Is there any line "down" that we can move the cursor to?
                for row_idx in range(self._cur_row+1, len(self._cursor_positions)):
                    if len(self._cursor_positions[row_idx]):
                        self._cur_row = row_idx
                        break
                
                self._lcd.set_cursor_pos(self._cur_row, self._cursor_positions[self._cur_row][self._cur_field])

    def cursor_up(self):
        if self._edit_mode:
            # Get the subfield definition being edited
            edit_subfield = self._screen_def[self._edit_item[0]][self._edit_item[1]]
            if self._debug:
                print("Subfield being edited: {0}".format(edit_subfield))
            # Get the current cursor position
            save_cursor = self._lcd.cursor_pos()
            # Get the edit value
            edit_value = edit_subfield['text']
            if not self._edit_numbers:
                # Get the character from the text element that we're currently on
                if self._edit_pos > (len(edit_value)-1):
                    cur_char = ""
                else:
                    cur_char = edit_value[self._edit_pos]
                char_index = self._cur_character_set.find(cur_char)
                if char_index > 0:
                    cur_char = self._cur_character_set[char_index-1]
                else:
                    cur_char = self._cur_character_set[-1]
                # Update the character in the edit value with the new value
                edit_value = edit_value[:self._edit_pos] + cur_char + edit_value[self._edit_pos+1:]
            # When updating numbers of there is a min or max value and the new value is outside of that range
            # then don't update the number
            else:
                if "max_value" in edit_subfield:
                    if (edit_value+1) <= edit_subfield["max_value"]:
                        edit_value +=1 
                else:
                    edit_value +=1
            edit_subfield['text'] = edit_value
            # If editing numbers replace the entire line
            if self._edit_numbers:
                lcd_line = ("{0:" + str(self._num_characters) + "." + str(self._num_characters) + "}").format(str(edit_value))
                self._lcd.print(lcd_line)
            else:
                self._lcd.print(cur_char)
            # Reset the cursor position
            self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
        else:
            # If the new current row is less than the first visible row and
            # the first visible row is > 0 then reload
            # the screen with the appropriate offset
            if (self._cur_row-1) < self._first_visible_row and self._last_visible_row > 0:
                self.load_screen(self._screen_def, self._first_visible_row-1)
            else:
                # Can we move up?
                for row_idx in range(self._cur_row-1, -1, -1):
                    if len(self._cursor_positions[row_idx]):
                        self._cur_row = row_idx
                        break
                self._lcd.set_cursor_pos(self._cur_row, self._cursor_positions[self._cur_row][self._cur_field])

    def cursor_left(self):
        if self._edit_mode:
            if self._edit_pos > 0 and not self._edit_numbers:
                self._edit_pos -= 1
                self._lcd.set_cursor_pos(self._edit_item[0], self._edit_pos)
        else:
            # Can we move left?
            if self._cur_field > 0:
                self._cur_field -= 1
            self._lcd.set_cursor_pos(self._cur_row, self._cursor_positions[self._cur_row][self._cur_field])
            
    def cursor_right(self):
     
        if self._edit_mode:
            if not self._edit_numbers:
                # Get the subfield definition being edited
                edit_subfield = self._screen_def[self._edit_item[0]][self._edit_item[1]]
                if 'max_len' in edit_subfield:
                    max_char = edit_subfield['max_len']
                else:
                    max_char = self._num_characters
                if self._edit_pos < (max_char-1):
                    self._edit_pos += 1
                    self._lcd.set_cursor_pos(self._edit_item[0], self._edit_pos)
                # If the new position is past the end of the text value and we're editing numbers
                # then append a 0 to the new position
                if self._edit_pos > (len(str(edit_subfield["text"]))-1) and self._edit_numbers:
                    new_text = str(edit_subfield["text"])
                    new_text += self._numbers[0]
                    edit_subfield["text"] = int(new_text)
                    if self._debug:
                        print("New edit subfield: {0}".format(edit_subfield))
                    save_cursor = self._lcd.cursor_pos()
                    self._lcd.print(self._numbers[0])
                    self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
        else:
            # Can we move right?
            if self._cur_field < (len(self._cursor_positions[self._cur_row])-1):
                self._cur_field += 1
            self._lcd.set_cursor_pos(self._cur_row, self._cursor_positions[self._cur_row][self._cur_field])

    def enter(self):
        subfield = self._screen_def[(self._cur_row+self._first_visible_row)][self._cur_field]
        if "select" in subfield and subfield["select"] is True:
            # In edit mode and entering numbers ensure the value is between the min and max values if specified
            if self._edit_mode and self._edit_numbers:
                num_value = subfield["text"]
                save_cursor = self._lcd.cursor_pos()
                if "min_value" in subfield and num_value < subfield["min_value"]:
                    self.load_status_line("Value must be >= {0}".format(subfield["min_value"]))
                    self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
                    return None
                if "max_value" in subfield and num_value > subfield["max_value"]:
                    self.load_status_line("Value must be <= {0}".format(subfield["max_value"]))
                    self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
                    return None            
            return subfield

    # Backspace key. This key only does something in edit mode
    def backspace(self):
        if self._edit_mode:
            # Get the subfield definition being edited
            edit_subfield = self._screen_def[self._edit_item[0]][self._edit_item[1]]
            if self._debug:
                print("Subfield being edited: {0}".format(edit_subfield))
            # If there is any text then delete the last one
            if self._edit_numbers:
                text = str(edit_subfield["text"])
            else:
                text = edit_subfield["text"]
            if len(text):
                text = text[:-1]
            if self._edit_numbers:
                edit_subfield["text"] = int(text)
            else:
                edit_subfield["text"] = text
            # Save the current cursor position
            save_cursor = self._lcd.cursor_pos()
            # Clear the last character in the edit field and move back 1 space
            self._lcd.print(" ")
            self._edit_pos -= 1
            self._lcd.set_cursor_pos(save_cursor[0], self._edit_pos)
                
            
    # Switch between character sets when in edit/alpha
    def sel_character_set(self):
        if self._edit_mode and not self._edit_numbers:
            if self._cur_character_set == self._alpha_lower_characters:
                self._cur_character_set = self._alpha_upper_characters
                self._char_set_key_label = self._char_set_key + "=Symb "
            elif self._cur_character_set == self._alpha_upper_characters:
                self._cur_character_set = self._symbol_characters
                self._char_set_key_label = self._char_set_key + "=Numb "
            elif self._cur_character_set == self._symbol_characters:
                self._cur_character_set = self._numbers
                self._char_set_key_label = self._char_set_key + "=Lowr "
            else:
                self._cur_character_set = self._alpha_lower_characters
                self._char_set_key_label = self._char_set_key + "=Uppr "
            if self._debug:
                print("Setting status text: {0}".format(self._char_set_key_label))
            # Save the cursor position
            save_cursor = self._lcd.cursor_pos()
            self.load_status_line(self._char_set_key_label + self._bkspc_key + "=Bkspc", line_number=(self._num_lines-2))
            self.load_status_line("Ent=Save")
            self._lcd.set_cursor_pos(save_cursor[0], save_cursor[1])
                        
    def _set_character_set(self, edit_text, position):
        # When editing an alpha type the character set can be upper, lower, symbol or number
        if self._edit_numbers == False:
            # Get the first character from the text and use that to determine what character set
            # we should use as the first set
            if len(edit_text):
                if self._debug:
                    print("Looking for character {0}".format(edit_text[position]))
                if self._alpha_lower_characters.find(edit_text[position]) >= 0:
                    self._cur_character_set = self._alpha_lower_characters
                    self._char_set_key_label = self._char_set_key + "=Uppr "
                elif self._alpha_upper_characters.find(edit_text[position]) >= 0:
                    self._cur_character_set = self._alpha_upper_characters
                    self._char_set_key_label = self._char_set_key + "=Symb "
                elif self._symbol_characters.find(edit_text[position]) >= 0:
                    self._cur_character_set = self._symbol_characters
                    self._char_set_key_label = self._char_set_key + "=Numb "
                elif self._numbers.find(edit_text[position]) >= 0:
                    self._cur_character_set = self._numbers
                    self._char_set_key_label = self._char_set_key + "=Lowr "
            if not self._cur_character_set:
                self._cur_character_set = self._alpha_lower_characters
                self._char_set_key_label = self._char_set_key + "=Lowr "
        # When editing number type field the character set can only be numbers            
        else:
            self._cur_character_set = self._numbers

        if self._debug:
            print("Current character set: {0}".format(self._cur_character_set))
            
    def print_debug(self):

        print(self._cursor_positions)
        print("Cursor row: {0}".format(self._cur_row))
        print("Cursor field: {0}".format(self._cur_field))

        # Print cursor text
        if self._cur_row >= 0:
            print("Cursor: {0}".format(self._screen_def[self._cur_row][self._cur_field]["text"]))