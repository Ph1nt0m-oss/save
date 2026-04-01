function App() {
    const [items, setItems] = React.useState(() => {
        const savedItems = localStorage.getItem('shoppingList');
        return savedItems ? JSON.parse(savedItems) : [];
    });
    const [input, setInput] = React.useState('');

    React.useEffect(() => {
        localStorage.setItem('shoppingList', JSON.stringify(items));
    }, [items]);

    const addItem = () => {
        if (input.trim() !== '') {
            setItems([...items, { name: input, checked: false }]);
            setInput('');
        }
    };

    const removeItem = (index) => {
        const newItems = items.filter((_, i) => i !== index);
        setItems(newItems);
    };

    const toggleItem = (index) => {
        const newItems = items.map((item, i) => (
          i === index ? { ...item, checked: !item.checked } : item
        ));
        setItems(newItems);
    };

    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">Liste de Courses</h1>
            <div className="flex mb-4">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ajouter un article"
                    className="w-full p-2 rounded-lg border border-white bg-[#0F0F13] text-white"
                />
                <button
                    onClick={addItem}
                    className="p-2 ml-2 bg-[#E4FF00] text-black rounded-lg shadow-lg hover:bg-[#00FF66] transition-all"
                >
                    Ajouter
                </button>
            </div>
            <ul className="space-y-3">
                {items.map((item, index) => (
                    <li key={index}
                        className={`flex justify-between items-center p-3 bg-[#0F0F13] rounded-lg shadow-[0_0_30px_rgba(228,255,0,0.3)] ${item.checked ? 'line-through text-secondary' : 'text-white'}`}
                    >
                        <span onClick={() => toggleItem(index)} className="cursor-pointer">
                            {item.name}
                        </span>
                        <button
                            onClick={() => removeItem(index)}
                            className="bg-red-500 text-white p-2 rounded-lg hover:bg-red-700 transition-all"
                        >
                            Supprimer
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);