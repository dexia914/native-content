from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = Field(default="deepseek", alias="LLM_PROVIDER")
    llm_model: str = Field(default="deepseek-chat", alias="LLM_MODEL")
    llm_base_url: str = Field(default="https://api.deepseek.com", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")

    image_provider: str = Field(default="dalle", alias="IMAGE_PROVIDER")
    image_model: str = Field(default="gpt-image-1", alias="IMAGE_MODEL")
    image_base_url: str = Field(default="https://api.openai.com/v1", alias="IMAGE_BASE_URL")
    image_api_key: str = Field(default="", alias="IMAGE_API_KEY")
    image_size: str = Field(default="1024x1024", alias="IMAGE_SIZE")
    image_workspace: str = Field(default="", alias="IMAGE_WORKSPACE")
    no_text_in_image: bool = Field(default=True, alias="NO_TEXT_IN_IMAGE")

    output_dir: str = Field(default="outputs", alias="OUTPUT_DIR")
    font_path: str = Field(default="", alias="FONT_PATH")

    xhs_login_state_path: str = Field(default=".auth/xiaohongshu.json", alias="XHS_LOGIN_STATE_PATH")
    xhs_headless: bool = Field(default=False, alias="XHS_HEADLESS")
    xhs_base_url: str = Field(default="https://creator.xiaohongshu.com", alias="XHS_BASE_URL")


settings = Settings()
