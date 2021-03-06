# coding=utf-8
"""Objects related to ingredients and stock"""
import logging
from typing import Optional, List, Any, Dict, Union

from psycopg2 import sql

import rses_errors
from rses_connections import db

log = logging.getLogger(__name__)


class IngredientType:
    """For shopping list organization and filtering"""
    def __init__(self, *, ingredient_type_id: Optional[int]=None, name: Optional[str]=None) -> None:
        self._id: Optional[int] = ingredient_type_id
        self._name: Optional[str] = name
        if not self._id:
            self.create()
        elif not self._name:
            self.__load_from_db()

    def __str__(self):
        return f"Ingredient type '{self.name}'"

    def __repr__(self):
        return f'IngredientType(id={self.id}, name={self.name})'

    def __eq__(self, other):
        return repr(self) == repr(other)

    @property
    def id(self) -> int:
        """Id of the ingredient type in the database, cannot be modified"""
        return self._id

    @property
    def name(self) -> str:
        """Name of the ingredient type as shown the the user"""
        return self._name

    @name.setter
    def name(self, new_name: str):
        log.debug("Updating name of %s, new name: %s", str(self), new_name)
        query = """
        UPDATE ingredient_type
        SET name = %s
        WHERE id = %s
        """
        db.update(query, new_name, self._id)
        self._name = new_name

    def exists(self) -> bool:
        """Whether the ingredient type exists"""
        query = """
        SELECT * 
        FROM ingredient_type
        WHERE name = %s
        """
        res = db.select(query, self._name)
        if res:
            log.debug('%s was found in the database', self._name)
        else:
            log.debug('%s was not found in the database', self._name)
        return bool(res)

    def create(self):
        """Creates an ingredient type"""
        log.debug('Trying to create new %s', str(self))
        if self.exists() or self._id:
            raise rses_errors.AlreadyExists(self)
        if self._name is None:
            raise rses_errors.MissingParameter('name')
        query = """
        INSERT INTO ingredient_type (id, name)
        VALUES (DEFAULT, %s)
        RETURNING *
        """
        self._id = db.insert(query, self._name).id
        log.debug('Created, new id: %s', self.id)

    def delete(self):
        """Deletes an ingredient type"""
        log.debug('Deleting %s', str(self))
        if not self.exists():
            raise rses_errors.DoesNotExist(IngredientType, identifier=self._name)
        query = """
        DELETE FROM ingredient_type
        WHERE id = %s
        """
        db.delete(query, self._id)

    def items(self) -> List['Ingredient']:
        """All ingredients of this type"""
        log.debug('Getting all ingredients of %s', str(self))
        query = """
        SELECT id as id
        FROM ingredient
        WHERE ingredient_type = %s
        """
        res = db.select_all(query, self._id)
        ingredients = list()
        for item in res:
            ingredients.append(Ingredient(ingredient_id=item.id))
        return ingredients

    def __load_from_db(self):
        """Loads ingredient type from the database"""
        query = """
        SELECT name
        FROM ingredient_type
        WHERE id = %s
        """
        res = db.select(query, self._id)
        self._name = res.name

    @classmethod
    def load_by_name(cls, name):
        """Loads ingredient type by name"""
        query = """
        SELECT id AS id
        FROM ingredient_type
        WHERE name = %s
        """
        res = db.select(query, name)
        if res is None:
            raise rses_errors.DoesNotExist(IngredientType, name)
        return cls(ingredient_type_id=res.id)

    @property
    def json_dict(self) -> Dict[str, Union[int, str]]:
        """Returns dictionary that can be jsonified and served by the api"""
        return dict(id=self.id, name=self.name)


class Ingredient:
    """An ingredient to buy and use in recipes"""
    def __init__(
            self, *,
            ingredient_id: Optional[int]=None,
            name: Optional[str]=None,
            unit: Optional[str]=None,
            ingredient_type: Optional[IngredientType]=None,
            suggestion_threshold: Optional[float]=0.0,
            rebuy_threshold: Optional[float]=0.0,
            durability: Optional[int]=None
    ) -> None:
        """
        :param ingredient_id            Identifier for an ingredient, assigned be the database on creation
        :param name:                    The name of the ingredient, as will be display everywhere
        :param unit:                    The measurable unit of the ingredient, can be virtually anything
        :param ingredient_type:         The type if ingredient that the item belongs to
        :param suggestion_threshold:    When the shopping system will recommend you to maybe purchase
        :param rebuy_threshold:         When the shopping system tells you to absolutely buy it next time you see it
        :param durability:              If specified, calculates the expiration date based on the date of purchase
        """
        self._id: Optional[int] = ingredient_id
        self._name: str = name
        self._unit: Optional[str] = unit
        self._type: Optional[IngredientType] = ingredient_type
        self._suggestion_threshold: Optional[float] = suggestion_threshold
        self._rebuy_threshold: Optional[float] = rebuy_threshold
        self._durability: Optional[int] = durability
        if not self._id:
            self.create()
        elif not any(
                [self._name, self._unit, self._type, self._suggestion_threshold,
                 self._rebuy_threshold, self._durability]
        ):
            self.__load_from_db()

    @property
    def id(self) -> int:
        """Id of the ingredient in the database, cannot be modified"""
        return self._id

    @property
    def name(self) -> str:
        """Name of the ingredient as shown the the user"""
        return self._name

    @name.setter
    def name(self, new_name: str):
        self._name = self.__updater('name', new_name)

    @property
    def unit(self) -> str:
        """Unit in which the ingredient is measured - not only in recipes, but also in shopping lists"""
        return self._unit

    @unit.setter
    def unit(self, new_unit: str):
        self._unit = self.__updater('unit', new_unit)

    @property
    def type(self) -> IngredientType:
        """Type of the ingredient, foreign key to Ingredient Type in the database"""
        return self._type

    @type.setter
    def type(self, new_type: IngredientType):
        self.__updater('type', new_type.id)
        self._type = new_type

    @property
    def suggestion_threshold(self) -> float:
        """Threshold, at which shopping list will suggest buying"""
        return self._suggestion_threshold

    @suggestion_threshold.setter
    def suggestion_threshold(self, new_threshold: float):
        self._suggestion_threshold = self.__updater('suggestion_threshold', new_threshold)

    @property
    def rebuy_threshold(self) -> float:
        """Threshold, at which shopping list will add it as 'to buy'"""
        return self._rebuy_threshold

    @rebuy_threshold.setter
    def rebuy_threshold(self, new_threshold: float):
        self._rebuy_threshold = self.__updater('rebuy_threshold', new_threshold)

    @property
    def durability(self) -> int:
        """If no expiration date was set in the stock table, how many days can this usually last to calculate it"""
        return self._durability

    @durability.setter
    def durability(self, new_durability: int):
        self._durability = self.__updater('durability', new_durability)

    @property
    def average_price(self) -> float:
        """Average price of the ingredient"""
        query = """
        SELECT avg(price) as average
        FROM stock
        WHERE ingredient = %s 
        ORDER BY time_bought DESC 
        LIMIT 30
        """
        return db.select(query, self._name).average

    @property
    def in_stock(self) -> float:
        """
        Counts total of amount left in table stock for ingredient
        
        :return:    How much is left in stock
        """
        query = """
        SELECT count(amount_left) AS amount
        FROM stock
        WHERE ingredient = %s
        """
        res = db.select(query, self._id)
        return res.amount

    def __str__(self):
        return f'Ingredient {self._name}'

    def __repr__(self):
        return f'Ingredient(id={self._id}, name={self._name}, unit={self._unit}, type={repr(self._type)}, ' \
               f'suggestion_threshold={self._suggestion_threshold}, rebuy_threshold={self._rebuy_threshold}'

    def exists(self) -> bool:
        """
        :return:    If the ingredient exists
        """
        query = """
        SELECT * 
        FROM ingredient
        WHERE name = %s
        """
        res = db.select(query, self._name)
        if res:
            log.debug('%s was found in the database', self._name)
        else:
            log.debug('%s was not found in the database', self._name)
        return bool(res)

    def create(self):
        """
        Creates the ingredient, requires to have type and unit specified.
        
        Default thresholds are 0 and no durability is set.
        """
        log.debug('Trying to create new %s', str(self))
        required_params = dict(type=self._type, unit=self._unit, ingredient_type=self._type)
        for name, param in required_params.items():
            if param is None:
                rses_errors.MissingParameter(name)
        if self.exists():
            raise rses_errors.AlreadyExists(self)
        query = """
        INSERT INTO ingredient (name, unit, ingredient_type, suggestion_threshold, rebuy_threshold, durability)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id"""
        self._id = db.insert(query, self._name, self._unit, self._type.id, self._suggestion_threshold,
                             self._rebuy_threshold, self._durability).id
        log.debug('Created, new id: %s', self._id)

    def remove_stock(self, amount: float) -> None:
        """Removes amount of ingredient from the stock, from the oldest"""
        log.debug('Removing %s%s of %s from stock', amount, self._unit, str(self))
        query_select = """
        SELECT id, amount_left
        FROM stock
        WHERE amount_left > 0
        ORDER BY time_bought DESC
        LIMIT 1
        """
        res = db.select(query_select)
        can_remove = res.amount_left if res.amount_left >= amount else amount
        query_update = """
        UPDATE stock
        SET amount_left = amount_left - %s
        WHERE id = %s
        """
        db.delete(query_update, res.id)
        amount -= can_remove
        # FIXME > instead of != in case an error happened somewhere, after testing this, it can be replaced
        if amount > 0:
            log.debug('There is still %s%s left to remove, calling recursively', amount, self._unit)
            self.remove_stock(amount)

    def delete(self):
        """Deletes an ingredient type"""
        log.debug('Deleting %s', str(self))
        if not self.exists():
            raise rses_errors.DoesNotExist(Ingredient, identifier=self._name)
        query = """
        DELETE FROM ingredient
        WHERE id = %s
        """
        db.delete(query, self._id)

    def __updater(self, column: str, new_value: Any) -> Any:
        """Updates the Ingredient entry's value for specified column"""
        log.debug('Updating ingredient column %s from %s to %s', column, getattr(self, 'column'), new_value)
        query = sql.SQL("""
        UPDATE ingredient
        SET {} = %s
        WHERE id = %s
        """).format(sql.Identifier(column))
        db.update(query, new_value, self._id)
        return new_value

    def __load_from_db(self):
        """Loads the ingredient from the database"""
        query = """
        SELECT name, unit, ingredient_type, suggestion_threshold, rebuy_threshold, durability
        FROM ingredient
        WHERE id = %s
        """
        res = db.select(query, self._id)
        self._name = res.name
        self._unit = res.unit
        self._type = IngredientType(ingredient_type_id=res.ingredient_type)
        self._suggestion_threshold = res.suggestion_threshold
        self._rebuy_threshold = res.rebuy_threshold
        self._durability = res.durability

    @classmethod
    def load_by_name(cls, name):
        """Loads the ingredient from the database"""
        query = """
        SELECT id as id
        FROM ingredient
        WHERE name = %s
        """
        res = db.select(query, name)
        return cls(ingredient_id=res.id)

    @property
    def json_dict(self) -> Dict[str, Union[int, str]]:
        """Returns dictionary that can be jsonified and served by the api"""
        return dict(id=self.id, name=self.name, unit=self.unit, type=self.type,
                    suggestion_threshold=self.suggestion_threshold, rebuy_threshold=self.rebuy_threshold,
                    durability=self.durability)


class IngredientTypeListing:
    """class for total and individual items of Ingredient Type table"""

    @property
    def total(self) -> int:
        """How many ingredient types there are in the database"""
        query = """
        SELECT COUNT(*) AS total
        FROM ingredient_type
        """
        return db.select(query).total

    @staticmethod
    def show(limit: int=50, offset: int=0, name_filter: str= '') -> List[Dict[str, Union[int, str]]]:
        """
        Lists ingredient types
        
        :param limit:           How many to list
        :param offset:          Select offset
        :param name_filter:     If the name should be filtered at all, will be lowered automatically
        :return:                Filtered and limited ingredient types as dictionaries
        """
        name_filter = name_filter.lower()
        query = """
        SELECT id, name
        FROM ingredient_type
        WHERE NAME LIKE %s
        ORDER BY name ASC
        LIMIT %s
        OFFSET %s
        """
        name_filter = f'%{name_filter}%'.lower()
        res = db.select_all(query, name_filter, limit, offset)
        return [IngredientType(ingredient_type_id=item.id, name=item.name).json_dict for item in res]


class IngredientListing:
    """class for total and individual items of Ingredient Type table"""

    @property
    def total(self) -> int:
        """How many ingredient types there are in the database"""
        query = """
        SELECT COUNT(*) AS total
        FROM ingredient
        """
        return db.select(query).total

    @staticmethod
    def show(limit: int = 50, offset: int = 0,
             wanted_filters: Optional[dict] = None) -> List[Dict[str, Union[int, str]]]:
        """
        Lists ingredient types

        :param limit:           How many to list
        :param offset:          Select offset
        :param wanted_filters:  Dictionary of items to be filtered
        :return:                Filtered and limited ingredient types as dictionaries
        """
        filters = dict(
            name='',
            unit='',
            ingredient_type=''
        )
        if wanted_filters is not None:
            filters.update(wanted_filters)
        query = """
        SELECT id, name, unit, ingredient_type, suggestion_threshold, rebuy_threshold, durability
        FROM ingredient
        WHERE 
          name LIKE %s
          AND unit like %s
          AND ingredient_type LIKE %s
        ORDER BY name ASC
        LIMIT %s
        OFFSET %s
        """
        name_filter = f'%{filters["name"]}%'.lower()
        unit_filter = f'%{filters["unit"]}%'.lower()
        ingredient_type_filter = f'%{filters["ingredient_type"]}%'.lower()
        res = db.select_all(query, name_filter, unit_filter, ingredient_type_filter, limit, offset)
        return [Ingredient(
            ingredient_id=item.id, name=item.name, unit=item.unit, ingredient_type=item.ingredient_type,
            suggestion_threshold=item.suggestion_threshold, rebuy_threshold=item.rebuy_threshold,
            durability=item.durability
        ).json_dict for item in res]
