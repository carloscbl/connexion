from unittest.mock import MagicMock

import pytest
from connexion.apis.flask_api import FlaskApi
from connexion.decorators.validation import ParameterValidator
from connexion.json_schema import (Draft4RequestValidator,
                                   Draft4ResponseValidator)
from jsonschema import ValidationError


def test_get_valid_parameter():
    result = ParameterValidator.validate_parameter('formdata', 20, {'type': 'number', 'name': 'foobar'})
    assert result is None


def test_get_valid_parameter_with_required_attr():
    param = {'type': 'number', 'required': True, 'name': 'foobar'}
    result = ParameterValidator.validate_parameter('formdata', 20, param)
    assert result is None


def test_get_valid_path_parameter():
    param = {'required': True, 'schema': {'type': 'number'}, 'name': 'foobar'}
    result = ParameterValidator.validate_parameter('path', 20, param)
    assert result is None


def test_get_missing_required_parameter():
    param = {'type': 'number', 'required': True, 'name': 'foo'}
    result = ParameterValidator.validate_parameter('formdata', None, param)
    assert result == "Missing formdata parameter 'foo'"


def test_get_x_nullable_parameter():
    param = {'type': 'number', 'required': True, 'name': 'foo', 'x-nullable': True}
    result = ParameterValidator.validate_parameter('formdata', 'None', param)
    assert result is None


def test_get_nullable_parameter():
    param = {'schema': {'type': 'number', 'nullable': True},
             'required': True, 'name': 'foo'}
    result = ParameterValidator.validate_parameter('query', 'null', param)
    assert result is None


def test_get_explodable_object_parameter():
    param = {'schema': {'type': 'object', 'additionalProperties': True},
             'required': True, 'name': 'foo', 'style': 'deepObject', 'explode': True}
    result = ParameterValidator.validate_parameter('query', {'bar': 1}, param)
    assert result is None
    
    
def test_get_valid_parameter_with_enum_array_header():
    value = 'VALUE1,VALUE2'
    param = {'schema': {'type': 'array', 'items': {'type': 'string', 'enum': ['VALUE1', 'VALUE2']}},
             'name': 'test_header_param'}
    result = ParameterValidator.validate_parameter('header', value, param)
    assert result is None


def test_invalid_type(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr('connexion.decorators.validation.logger', logger)
    result = ParameterValidator.validate_parameter('formdata', 20, {'type': 'string', 'name': 'foo'})
    expected_result = """20 is not of type 'string'

Failed validating 'type' in schema:
    {'type': 'string', 'name': 'foo'}

On instance:
    20"""
    print("ZZZZZZ",result)
    print("ZZZZZZ2",expected_result)
    assert result == expected_result
    logger.info.assert_called_once()


def test_invalid_type_value_error(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr('connexion.decorators.validation.logger', logger)
    value = {'test': 1, 'second': 2}
    result = ParameterValidator.validate_parameter('formdata', value, {'type': 'boolean', 'name': 'foo'})
    assert result == "Wrong type, expected 'boolean' for formdata parameter 'foo'"


def test_enum_error(monkeypatch):
    logger = MagicMock()
    monkeypatch.setattr('connexion.decorators.validation.logger', logger)
    value = 'INVALID'
    param = {'schema': {'type': 'string', 'enum': ['valid']},
             'name': 'test_path_param'}
    result = ParameterValidator.validate_parameter('path', value, param)
    assert result.startswith("'INVALID' is not one of ['valid']")


def test_support_nullable_properties():
    schema = {
        "type": "object",
        "properties": {"foo": {"type": "string", "x-nullable": True}},
    }
    try:
        Draft4RequestValidator(schema).validate({"foo": None})
    except ValidationError:
        pytest.fail("Shouldn't raise ValidationError")


def test_support_nullable_properties_raises_validation_error():
    schema = {
        "type": "object",
        "properties": {"foo": {"type": "string", "x-nullable": False}},
    }

    with pytest.raises(ValidationError):
        Draft4RequestValidator(schema).validate({"foo": None})


def test_support_nullable_properties_not_iterable():
    schema = {
        "type": "object",
        "properties": {"foo": {"type": "string", "x-nullable": True}},
    }
    with pytest.raises(ValidationError):
        Draft4RequestValidator(schema).validate(12345)


def test_nullable_enum():
    schema = {
        "enum": ["foo", 7],
        "nullable": True
    }
    try:
        Draft4RequestValidator(schema).validate(None)
    except ValidationError:
        pytest.fail("Shouldn't raise ValidationError")


def test_nullable_enum_error():
    schema = {
        "enum": ["foo", 7]
    }
    with pytest.raises(ValidationError):
        Draft4RequestValidator(schema).validate(None)


def test_writeonly_value():
    schema = {
        "type": "object",
        "properties": {"foo": {"type": "string", "writeOnly": True}},
    }
    try:
        Draft4RequestValidator(schema).validate({"foo": "bar"})
    except ValidationError:
        pytest.fail("Shouldn't raise ValidationError")


def test_writeonly_value_error():
    schema = {
        "type": "object",
        "properties": {"foo": {"type": "string", "writeOnly": True}},
    }
    with pytest.raises(ValidationError):
        Draft4ResponseValidator(schema).validate({"foo": "bar"})


def test_writeonly_required():
    schema = {
        "type": "object",
        "required": ["foo"],
        "properties": {"foo": {"type": "string", "writeOnly": True}},
    }
    try:
        Draft4RequestValidator(schema).validate({"foo": "bar"})
    except ValidationError:
        pytest.fail("Shouldn't raise ValidationError")


def test_writeonly_required_error():
    schema = {
        "type": "object",
        "required": ["foo"],
        "properties": {"foo": {"type": "string", "writeOnly": True}},
    }
    with pytest.raises(ValidationError):
        Draft4RequestValidator(schema).validate({"bar": "baz"})


def test_formdata_extra_parameter_strict():
    """Tests that connexion handles explicitly defined formData parameters well across Swagger 2
    and OpenApi 3. In Swagger 2, any formData parameter should be defined explicitly, while in
    OpenAPI 3 this is not allowed. See issues #1020 #1160 #1340 #1343."""
    request = MagicMock(form={'param': 'value', 'extra_param': 'extra_value'})

    # OAS3
    validator = ParameterValidator([], FlaskApi, strict_validation=True)
    errors = validator.validate_formdata_parameter_list(request)
    assert not errors

    # Swagger 2
    validator = ParameterValidator([{'in': 'formData', 'name': 'param'}], FlaskApi,
                                   strict_validation=True)
    errors = validator.validate_formdata_parameter_list(request)
    assert errors
