# Update Journal

## 2026-01-09 - Session Start

### Task: Refactor attribute handling to support selection and transfer like channels
- Replace metadata_display (QTextEdit) with attribute list (read-only)
- Support multi-line selection
- Add "Add Selected to the Attributes" button
- Replace "Import From Source" button with "Edit Attribute" button

### Current Status
- Created journal file
- Analyzed current codebase structure
- Identified files to modify:
  1. app/ui/main_window.py - Replace metadata_display with new attribute list
  2. app/ui/widgets/attribute_editor.py - Add Edit Attribute button
  3. Possibly new widget or model for read-only attribute list

### Plan
1. Create AttributeListModel (similar to ChannelListModel for read-only attributes)
2. Create read-only attribute list widget in input panel
3. Update main_window.py:
   - Replace metadata_display QTextEdit with new attribute list
   - Add "Add Selected to the Attributes" button
   - Update _on_sequence_selected to populate attribute list
4. Update AttributeEditor:
   - Replace "Import from Source" button with "Edit Attribute" button
   - Keep Add/Remove buttons

### Next Step
- Create AttributeListModel in qt_models.py
- Implement attribute list widget in input panel

## 2026-01-09 - Implementation Complete

### Changes Made:

1. **app/ui/models/qt_models.py**
   - Added AttributeListModel class for read-only attribute list display
   - Displays attributes as "name (type)" format
   - Supports multi-selection

2. **app/ui/models/__init__.py**
   - Exported AttributeListModel

3. **app/ui/main_window.py**
   - Imported AttributeListModel
   - Added attr_list_model to model initialization
   - Removed metadata_display (QTextEdit)
   - Added attribute_list (QListView) with multi-selection enabled
   - Added "Add Selected to Output Attributes" button
   - Updated _on_sequence_selected() to populate attribute_list instead of metadata_display
   - Removed _format_sequence_metadata() method (no longer needed)
   - Added _on_add_attributes_to_output() method to handle adding selected attributes
   - Removed signal connection for import_from_source_requested

4. **app/ui/widgets/attribute_editor.py**
   - Changed signal from import_from_source_requested to edit_attribute_requested
   - Replaced "Import from Source" button with "Edit Attribute" button
   - Changed _on_import_from_source() to _on_edit_attribute()
   - Added EditAttributeDialog class for editing existing attributes
   - Added dialog support for editing attribute values (name/type read-only)

### Testing Results
- All imports working correctly
- MainWindow instantiates successfully with new components
- attribute_list and attr_list_model attributes present
- _on_add_attributes_to_output() method exists
- AttributeEditor has _on_edit_attribute() method

### Status: COMPLETE
All requested changes have been successfully implemented and tested.

## 2026-01-09 - Additional Improvements

### Task: Three improvements requested
1. Source file attributes list should display values too (like "name: value")
2. Load sequence dialog should use settings.ini last_input_dir
3. Frame policy must be user controllable in options

### Changes Implemented:

1. **app/ui/models/qt_models.py - AttributeListModel.data()**
   - Changed display format from `"name (type)"` to `"name: value"`
   - Now shows both name and value for each attribute

2. **app/ui/main_window.py - _on_load_sequence()**
   - Added initial_dir parameter to QFileDialog.getExistingDirectory()
   - Uses self.settings.get_input_dir() to restore last used directory
   - Falls back to empty string if no previous directory saved

3. **app/ui/main_window.py - Frame Policy Control**
   - Imported FrameRangePolicy enum from core
   - Added frame_policy_combo (QComboBox) to Options tab
   - Added three options: "Stop at Shortest", "Hold Last Frame", "Process Available"
   - Added _on_frame_policy_changed() handler method
   - Maps display text to FrameRangePolicy enum values
   - Updates state.export_spec.frame_policy when user selects option

### Testing Results
- AttributeListModel displays format: "aperture: 2.8", "PixelAspectRatio: 1.0" ✓
- Settings reads last_input_dir correctly from settings.ini ✓
- Frame policy mapping works: Stop at Shortest -> STOP_AT_SHORTEST, etc. ✓
- MainWindow creates successfully with new frame_policy_combo ✓
- _on_frame_policy_changed handler method exists and callable ✓

### Status: COMPLETE
All three improvements have been successfully implemented and tested.

## 2026-01-09 - Output Attributes Refinements

### Task: Four improvements requested
1. Output attributes must support multiline selection (for multiline remove)
2. Remove the Source and Enabled columns
3. BUG: Double-click on attribute name deletes its name - disable in-list editing
4. Automatically add compression attribute on program load

### Changes Implemented:

1. **app/ui/models/qt_models.py - AttributeTableModel**
   - Changed COLUMNS from 5 to 3: ["Name", "Type", "Value"]
   - Updated data() method to only handle 3 columns
   - Updated flags() to disable editing (return flags without ItemIsEditable)
   - Updated setData() to return False (no editing allowed)

2. **app/ui/widgets/attribute_editor.py - AttributeEditor**
   - Changed table selection mode from SingleSelection to MultiSelection
   - Updated _on_remove_attribute() to handle multiple selected rows
   - Gets all selected indices and removes rows in reverse order to maintain correct indices

3. **app/ui/main_window.py - MainWindow**
   - Imported AttributeSpec and AttributeSource from core
   - Added _add_compression_attribute() method
   - Updated _load_settings() to call _add_compression_attribute()
   - Compression attribute created with current compression value from settings

### Testing Results
- MainWindow instantiates successfully with MultiSelection enabled ✓
- AttributeTableModel has 3 columns only ✓
- In-table editing disabled: ItemIsEditable=False, setData() returns False ✓
- Compression attribute auto-added on load with value "dwab" ✓
- Multiline removal works: select rows 0 and 2, removes them leaving only row 1 ✓

### Status: COMPLETE
All four improvements have been successfully implemented and tested.
