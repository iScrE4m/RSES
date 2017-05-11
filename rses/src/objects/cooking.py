# coding=utf-8
"""Objects related to cooking"""
from typing import List, Optional, Dict
import logging

import errors
from connections import db
from objects.stock import Ingredient

log = logging.getLogger(__name__)


class RecipeMeta:
    """Same as fucking ingredient, I HATE THIS"""
    pass


class RecipeCategory:
    """
    For recipe categorization
    """

    def __init__(self, *, recipe_category_id: Optional[int] = None, name: Optional[str] = None) -> None:
        self._id: Optional[int] = recipe_category_id
        self._name: Optional[str] = name
        if not self._id:
            self.create()
        elif not self._name:
            self.__load_from_db()

    def __str__(self):
        return f'Recipe Category {self._name}'

    def __repr__(self):
        return f'RecipeCategory(id={self._id}, name={self._name})'

    @property
    def id(self) -> int:
        """Id of the recipe category in the database, cannot be changed"""
        return self._id

    @property
    def name(self) -> str:
        """Name of the recipe category"""
        return self._name

    @name.setter
    def name(self, new_name):
        log.debug("Updating name of %s, new name: %s", str(self), new_name)
        query = """
        UPDATE recipe_category
        SET name = %s
        WHERE id = %s
        """
        db.update(query, new_name, self._id)
        self._name = new_name

    def exists(self) -> bool:
        """Checks whether the recipe category exists"""
        query = """
        SELECT * 
        FROM recipe_category
        WHERE name = %s
        """
        res = db.select(query, self._name)
        if res:
            log.debug('%s was found in the database', self._name)
        else:
            log.debug('%s was not found in the database', self._name)
        return bool(res)

    def create(self) -> None:
        """Creates the recipe category"""
        if self.exists() or self._id:
            raise errors.AlreadyExists(self)
        if self._name is None:
            raise errors.MissingParameter('name')
        query = """
        INSERT INTO recipe_category (id, name)
        VALUES (DEFAULT, %s)
        RETURNING *
        """
        self._id = db.insert(query, self._name).id
        log.debug('Created, new id: %s', self.id)

    def delete(self) -> None:
        """Deletes the recipe category"""
        if not self.exists():
            raise errors.DoesNotExist(RecipeCategory, identifier=self._name)
        query = """
        DELETE FROM recipe_category
        WHERE id = %s
        """
        db.delete(query, self._id)

    def items(self) -> List[RecipeMeta]:
        """All ingredients of this type"""
        query = """
        SELECT recipe
        FROM categorized_recipes
        WHERE category = %s
        """
        res = db.select_all(query, self._id)
        recipes = list()
        for item in res:
            recipes.append(Recipe(item.id))
        return recipes

    def __load_from_db(self):
        pass


class Recipe(RecipeMeta):
    """A recipe object"""
    def __init__(
            self,
            name: str,
            directions: str = '',
            picture: Optional[str] = None,
            prepare_time: Optional[int] = None,
            portions: Optional[int] = None,
            new: bool = False
    ) -> None:
        """
        :param name:            Name of the recipe
        :param directions:      How to make it :)
        :param picture:         Picture of the finished thing
        :param prepare_time:    Prepare time in minutes
        :param portions:        For how many portions should the recipe be shown
        :param new:             If it's a new recipe, so it doesn't try and load from database
        """
        self.name: str = name
        self.directions: str = directions
        self.picture: Optional[str] = picture
        self.prepare_time: Optional[int] = prepare_time
        self.portions: Optional[int] = portions
        self.ingredients: Dict[Ingredient, float] = dict()
        self.categories: List[RecipeCategory] = list()
        if not new:
            self.__load_from_db()

    @property
    def portion_price(self) -> float:
        """Price of a single portion based on ingredient average"""
        return self.current_price / self.portions

    @property
    def current_price(self) -> float:
        """Price of the whole meal based on ingredient average"""
        price: float = 0.0
        for ingredient, amount in self.ingredients:
            price += ingredient.average_price * amount
        return price

    def create(self) -> None:
        """Creates the recipe, has to be created before ingredients and categories are added!"""
        required_params = dict(portions=self.portions)
        for name, param in required_params:
            if param is None:
                errors.MissingParameter(name)
        query = """
        INSERT INTO recipe (id, directions, picture, prepare_time, portions) 
        VALUES (%s, %s, %s, %s, %s)
        """
        db.insert(query, self.name, self.directions, self.picture, self.prepare_time, self.portions)

    def delete(self) -> None:
        """Deletes the recipe"""
        query = """
        DELETE FROM recipe
        WHERE id = %s
        """
        db.delete(query, self.name)

    def add_ingredient(self, ingredient: Ingredient, amount: float) -> None:
        """Adds an ingredient to the recipe"""
        if ingredient in self.ingredients.keys():
            raise errors.AlreadyExists(ingredient, relation=self)
        query = """
        INSERT INTO recipe_ingredients (recipe, ingredient, amount) 
        VALUES (%s, %s, %s)
        """
        db.insert(query, self.name, ingredient.id, amount)
        self.ingredients[ingredient] = amount

    def remove_ingredient(self, ingredient: Ingredient) -> None:
        """Removes an ingredient from the recipe"""
        query = """
        DELETE FROM recipe_ingredients
        WHERE ingredient = %s 
        AND recipe = %s
        """
        db.delete(query, ingredient.id, self.name)
        self.ingredients.pop(ingredient, None)

    def add_category(self, category: RecipeCategory) -> None:
        """Adds the recipe into a category"""
        if category in self.categories:
            raise errors.AlreadyExists(category, relation=self)
        query = """
        INSERT INTO categorized_recipes (recipe, category) 
        VALUES (%s, %s)
        """
        db.insert(query, self.name, category.id)
        self.categories.append(category)

    def remove_category(self, category: RecipeCategory) -> None:
        """Removes the recipe from a category"""
        query = """
        DELETE FROM categorized_recipes
        WHERE recipe = %s
        AND category = %s
        """
        db.delete(query, self.name, category.id)

    def can_be_cooked(self) -> bool:
        """Checks whether the recipe can be cooked"""
        for ingredient, amount in self.ingredients:
            if amount > ingredient.in_stock:
                return False
        return True

    def cook(self) -> None:
        """Adds the recipe the a log of cooked recipes and subtracts the ingredients from stock"""
        if not self.can_be_cooked():
            raise errors.NotEnoughIngredients
        query = """
        INSERT INTO recipe_made (recipe, portions, price) 
        VALUES (%s, %s, %s)
        """
        db.insert(query, self.name, self.portions, self.current_price)
        for ingredient, amount in self.ingredients:
            ingredient.remove_stock(amount)

    def __load_from_db(self) -> None:
        wanted_portions: Optional[int] = self.portions

        query = """
        SELECT directions, picture, prepare_time, portions
        FROM recipe
        WHERE id = %s
        """
        res = db.select(query, self.name)
        self.directions = res.directions
        self.picture = res.picture,
        self.prepare_time = res.prepare_time
        self.portions = res.portions

        if wanted_portions is not None:
            adjust_portion: float = wanted_portions / self.portions
        else:
            adjust_portion = 1

        query_ingredients = """
        SELECT ingredient, amount
        FROM recipe_ingredients
        WHERE recipe = %s
        """
        res = db.select_all(query_ingredients, self.name)
        for i in res:
            ingredient = Ingredient(ingredient_id=i.ingredient)
            adjusted_amount: float = i.amount * adjust_portion
            self.ingredients[ingredient] = adjusted_amount
        query_categories = """
        SELECT category
        FROM categorized_recipes
        WHERE recipe = %s
        """
        res = db.select_all(query_categories, self.name)
        for category in res:
            self.categories.append(category.category)
