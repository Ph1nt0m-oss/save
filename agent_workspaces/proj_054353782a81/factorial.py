def factorial(n):
    """Calcule la factorielle d'un nombre entier positif.
    
    Args:
        n (int): Nombre entier positif
        
    Returns:
        int: Factorielle de n
        
    Raises:
        ValueError: Si n est négatif
        TypeError: Si n n'est pas un entier
    """
    if not isinstance(n, int):
        raise TypeError("n doit être un entier")
    if n < 0:
        raise ValueError("n doit être positif ou nul")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
