from pydantic import BaseModel

class RecipeBase(BaseModel):
    name: str
    ingredients: dict
    instructions: str
    nutritional_info: dict
    category: str

class RecipeCreate(RecipeBase):
    pass

class Recipe(RecipeBase):
    id: int

    class Config:
        from_attributes = True