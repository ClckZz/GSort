const categorize_btn = document.getElementById('categorize-btn')

async function categorizePosts() {
    const how_many = 10;

    const response = await fetch(
    `http://127.0.0.1:8000/categorize?how_many=${how_many}`
    );

    const data = await response.json();
    console.log(data);
}