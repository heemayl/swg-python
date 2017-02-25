import json
import yaml
import io
import os


class SwgParser:
    """
    SwgParser is a simple parser that extracts the Swagger API documentation throughout the given folders. The Swagger documentation must be written in
    YAML format. The specification is the same as the Swagger specification except a few details.
    **Exceptions**
    - A path definition **MUST** have the keys `method` and `path`. `method` key contains the standard HTTP methods and `path` is the path of the operation
    - A definition **MUST** have the `definition` key. A block that has the `definition` key will be treated as a definition. Obviously, the value for the key
      is the definition name.

    The documentation can be scattered throughout the project, `SwgParser` will walk thought the files and produce a single `swagger.json` or `swagger.yaml`
    file. For an example on how to use it, check the `example` folder. Beware, although it has valid Swagger documentation the project itself does nothing and
    doesn't work. `SwgParser` does not depend on any framework specific properties, so it can be used with any kind of project you want.
    """

    # This is the last end position of the swg block. This index is after the `@swg_end`
    _last_swg_block_position = 0

    # This is the main dictionary. It will stay the same unless @ref reset() method is called
    _swagger_dictionary = {}
    _folders = []

    def reset(self):
        """
        @brief      Resets all the parsing information. After this is called, you need to add folders to call the @ref compile() method
        """
        self._last_swg_block_position = 0
        self._swagger_dictionary = {}
        self._folders = []

    def add_folder(self, folder_path):
        """
        @brief      Adds the given folder_path to the list of folders to check for Swagger documentation.
                    If the folder already exists in the list, it is not added again.
        """

        if self._folders.count(folder_path) == 0:
            self._folders.append(folder_path)

    def compile(self):
        """
        @brief      Uses the _folders list to compile the Swagger documentation
        """

        for folder in self._folders:
            print(folder)
            self.compile_folder(folder)

    def compile_folder(self, directory):
        """
        @brief      Compiles a single directory. Only the files with the `py` extension is used.
        """

        for subdir, dirs, files in os.walk(directory):
            for file in files:
                filepath = subdir + os.sep + file
                if filepath.endswith(".py"):
                    self.compile_swagger_json(filepath)

    def compile_swagger_json(self, file_path):
        """
        @brief      Compile a single file
        """

        self._last_swg_block_position = 0

        file_content = open(file_path).read()

        while self.has_next():
            block = self.get_swg_block(file_content)
            if block is None:
                break

            self.put_definitions(block)
            self.put_swg_info(block)
            self.put_swg_path(block)

        return self._swagger_dictionary

    def get_swg_block(self, content):
        """
        @brief      Finds the block that starts with `@swg_begin` and ends with `@swg_end`
                    and returns the block within.
        @param      content  The original content
        @return     The swagger block as a dictionary. If there is not a swagger block, returns None
        """

        SWG_BEGIN = "@swg_begin"
        SWG_END = "@swg_end"
        block_dict = None

        if self._last_swg_block_position > -1:
            local_content = content[self._last_swg_block_position:]
            start = local_content.find(SWG_BEGIN)
            end = local_content.find(SWG_END)
            self._last_swg_block_position += end + len(SWG_END)

            if self._last_swg_block_position >= len(content) or start == -1 or end == -1:
                self._last_swg_block_position = -1
            else:
                block = local_content[start + len(SWG_BEGIN):end]
                block_dict = yaml.load(block)

        return block_dict

    def put_definitions(self, block):
        """
        @brief      Checks if the block is a definition block and if it is, constructs a definition block and updates the swagger dictionary
        """

        if self.is_swg_definition(block) is False:
            return

        definition_name = block.get('definition')
        block.pop('definition')
        block = {definition_name: block}
        if self._swagger_dictionary.get('definitions') is not None and self._swagger_dictionary.get('definitions').get(definition_name) is None:
            self._swagger_dictionary['definitions'].update(block)
        elif self._swagger_dictionary.get('definitions') is not None:
            self._swagger_dictionary['definitions'][definition_name] = block.get(definition_name)
        else:
            self._swagger_dictionary.update({'definitions': block})

    def put_swg_info(self, block):
        """
        @brief      If the block is an info block, updates the swagger dictionary. It does NOT check for duplicate input
        """

        if self.is_swg_info(block):
            self._swagger_dictionary.update(block)

    def put_swg_path(self, block):
        """
        @brief      If the block is a path block, updates the swagger dictionary.
        """

        method_name = block.get('method')
        path_name = block.get('path')
        block.pop('path')
        block = block.get(method_name)

        if self._swagger_dictionary.get('paths') is not None and self._swagger_dictionary['paths'].get(path_name) is not None:
            block = {method_name: block}
            self._swagger_dictionary['paths'][path_name].update(block)
        elif self._swagger_dictionary.get('paths') is not None:
            # If the `paths` key exists, but the HTTP method is not yet put here
            block = {path_name: {method_name: block}}
            self._swagger_dictionary['paths'].update(block)
        else:
            block = {'paths': {path_name: {method_name: block}}}
            self._swagger_dictionary.update(block)

    def is_swg_definition(self, swg_block):
        """
        @brief      A block is treated as a definition block If it has the `definition` key. The value of the `definition` key is the name of the definition.
        @param      swg_block  The swg block
        @return     True if swg definition, False otherwise.
        """

        return swg_block.get('definition') is not None

    def is_swg_path(self, swg_block):
        """
        @brief      If the block has a `method` key, it is treated as a path.
        @param      swg_block  The swg block
        @return     True if swg path, False otherwise.
        """

        return swg_block.get('method') is not None

    def is_swg_info(self, swg_block):
        """
        @brief      This is the block that describes the whole API. If an `info` key is present, it is treated as an info block.
        @param      swg_block  The swg block
        @return     True if swg root
        """

        return swg_block.get('info') is not None

    def has_next(self):
        return self._last_swg_block_position > -1

    def write_to_file(self, file_path, format='yaml', encoding='utf8'):
        """
        @brief      Write the generated swagger to a file. JSON and YAML formats are supported
        @param      file_path - The absolute file path
        @param      format Options are json and yaml
        @return     void
        """

        if len(self._swagger_dictionary) > 0:
            file = io.open(file_path, 'w', encoding=encoding)
            if format == 'yaml':
                file.write(yaml.dump(self._swagger_dictionary))
            else:
                file.write(json.dumps(self._swagger_dictionary))
            file.close()