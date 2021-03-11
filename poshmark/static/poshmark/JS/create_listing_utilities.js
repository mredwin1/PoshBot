$(document).ready(function () {
    $.fn.inputFilter = function(inputFilter) {
        return this.on("input keydown keyup mousedown mouseup select contextmenu drop", function() {
          if (inputFilter(this.value)) {
            this.oldValue = this.value;
            this.oldSelectionStart = this.selectionStart;
            this.oldSelectionEnd = this.selectionEnd;
          } else if (this.hasOwnProperty("oldValue")) {
            this.value = this.oldValue;
            this.setSelectionRange(this.oldSelectionStart, this.oldSelectionEnd);
          } else {
            this.value = "";
          }
        });
    };
    $('#id_main_category').change(function () {
        let main_category = $('#id_main_category').val();
        let secondary_category = $('#id_secondary_category');

        let choices;
        if (main_category === 'Women') {
            choices = ['Accessories', 'Bags', 'Dresses', 'Initimates & Sleepwear', 'Jackets & Coats', 'Jeans', 'Jewelry',
                'Makeup', 'Pants & Jumpsuits', 'Shoes', 'Shorts', 'Skirts', 'Sweaters', 'Swim', 'Tops', 'Skincare',
                'Hair','Bath & Body', 'Other']
        } else if (main_category === 'Men') {
            choices = ['Accessories', 'Bags', 'Jackets & Coats', 'Jeans', 'Pants', 'Shirts', 'Shoes', 'Shorts',
                'Suits & Blazers', 'Sweaters', 'Swim', 'Underwear & Socks', 'Grooming', 'Other']
        } else if (main_category === 'Kids') {
            choices = ['Accessories', 'Bottoms', 'Dresses', 'Jackets & Coats', 'Matching Sets', 'One Pieces', 'Pajamas',
                'Shirts & Tops', 'Shoes', 'Swim', 'Costumes', 'Bath, Skin & Hair', 'Toys', 'Other']
        } else if (main_category === 'Home') {
            choices = ['Accents', 'Bath', 'Bedding', 'Dining', 'Games', 'Holiday', 'Kitchen', 'Office',
                'Party Supplies', 'Storage & Organization', 'Wall Art', 'Other']
        } else if (main_category === 'Pets') {
            choices = ['Dog', 'Cat', 'Bird', 'Fish', 'Reptile', 'Small Pets', 'Other']
        }

        secondary_category.empty();
        secondary_category.append(`<option disabled selected>Select a Category</option>`);
        $.each(choices, function(index, value) {

            secondary_category.append(`<option value="${value}">${value}</option>`);
        });

    });
    $('#id_secondary_category').change(function () {
        let main_category = $('#id_main_category').val();
        let secondary_category = $('#id_secondary_category').val();
        let category = main_category + ' ' + secondary_category;
        let subcategory = $('#id_subcategory');
        let choices;
        console.log(category)
        if (category === 'Women Accessories') {
            choices = ['Belts', 'Face Masks', 'Glasses', 'Gloves & Mittens', 'Hair Accessories', 'Hats',
                'Hosiery & Socks', 'Key & Card Holders', 'Laptop Cases', 'Phone Cases', 'Scarves & Wraps', 'Sunglasses',
                'Tablet Cases', 'Umbrellas', 'Watches', 'None']
        } else if (category === 'Women Bags') {
            choices = ['Baby Bags', 'Backpacks', 'Clutches & Wristlets', 'Cosmetic Bags & Cases', 'Crossbody Bags',
                'Hobos', 'Laptop Bags', 'Mini Bags', 'Satchels', 'Shoulder Bags', 'Totes', 'Travel Bags', 'Wallets',
                'None']
        } else if (category === 'Women Dresses') {
            choices = ['Asymmetrical', 'Backless', 'High Low', 'Long Sleeve', 'Maxi', 'Midi', 'Mini', 'One Shoulder',
                'Prom', 'Strapless', 'Wedding', 'None']
        } else if (category === 'Women Intimates & Sleepware') {
            choices = ['Bandeaus', 'Bras', 'Chemises & Slips', 'Pijamas', 'Panties', 'Robes', 'Shapewear',
                'Sports Bras', 'None']
        } else if (category === 'Women Jackets & Coats') {
            choices = ['Blazers & Suit Jackets', 'Bomber Jackets', 'Capes', 'Jean Jackets', 'Leather Jackets',
                'Pea Coats', 'Puffers', 'Ski & Snow Jackets', 'Teddy Jackets', 'Trench Coats', 'Utility Jackets',
                'Varsity Jackets', 'Vests', 'None']
        } else if (category === 'Women Jeans') {
            choices = ['Ankle & Cropped', 'Boot Cut', 'Boyfriend', 'Flare & Wide Leg', 'High Rise', 'Jeggings',
                'Overalls', 'Skinny', 'Straight Leg', 'None']
        } else if (category === 'Women Jewelry') {
            choices = ['Bracelets', 'Brooches', 'Earrings', 'Necklaces', 'Rings', 'None']
        } else if (category === 'Women Makeup') {
            choices = ['Blush', 'Bronzer & Contour', 'Brows', 'Brushes & Tools', 'Concealer', 'Eye Primer', 'Eyeliner',
                'Eyeshadow', 'Foundation', 'Highlighter', 'Lashes', 'Lip Balm & Gloss', 'Lip Liner', 'Lipstick',
                'Mascara', 'Nail Tools', 'Press-On Nails', 'Primer', 'Setting Powder & Spray', 'None']
        } else if (category === 'Women Pants & Jumpsuits') {
            choices = ['Ankle & Cropped', 'Boot Cut & Flare', 'Capris', 'Jumpsuits & Rompers', 'Leggings', 'Pantsuits',
                'Skinny', 'Straight Leg', 'Track Pants & Joggers', 'Trousers', 'Wide Leg', 'None']
        } else if (category === 'Women Shoes') {
            choices = ['Ankle Boots & Booties', 'Athletic Shoes', 'Combat & Moto Boots', 'Espadrilles', 'Flats & Loafers', 'Heeled Boots', 'Heels', 'Lace Up Boots', 'Moccasins', 'Mules & Clogs', 'Over the Knee Boots', 'Platforms', 'Sandals', 'Slippers', 'Sneakers', 'Wedges', 'Winter & Rain Boots', 'None']
        } else if (category === 'Women Shorts') {
            choices = ['Athletic Shorts', 'Bermudas', 'Bike Shorts', 'Cargos', 'High Waist', 'Jean Shorts', 'Skorts', 'None']
        } else if (category === 'Women Skirts') {
            choices = ['A-Line or Full', 'Asymmetrical', 'Circle & Skater', 'High Low', 'Maxi', 'Midi', 'Mini', 'Pencil', 'Skirt Sets', 'None']
        } else if (category === 'Women Sweaters') {
            choices = ['Cardigans', 'Cowl & Turtlenecks', 'Crew & Scoop Necks', 'Off-the-Shoulder Sweaters', 'Shrugs & Ponchos', 'V-Necks', 'None']
        } else if (category === 'Women Swim') {
            choices = ['Bikinis', 'Coverups', 'One Pieces', 'Sarongs', 'None']
        } else if (category === 'Women Tops') {
            choices = ['Blouses', 'Bodysuits', 'Button Down Shirts', 'Camisoles', 'Crop Tops', 'Jerseys', 'Muscle Tees', 'Sweatshirts & Hoodies', 'Tank Tops', 'Tees - Long Sleeve', 'Tees - Short Sleeve', 'Tunics', 'None']
        } else if (category === 'Women Skincare') {
            choices = ['Acne & Blemish', 'Cleanser & Exfoliant', 'Eye Cream', 'Makeup Remover', 'Mask', 'Moisturizer', 'Peel', 'Serum & Face Oil', 'Suncare', 'Toner', 'Tools', 'None']
        } else if (category === 'Women Hair') {
            choices = ['Color', 'Conditioner', 'Hairspray', 'Heat Protectant', 'Shampoo', 'Styling', 'Tools', 'Treatment & Mask', 'Wigs & Extensions', 'None']
        } else if (category === 'Women Bath & Body') {
            choices = ['Bath Soak & Bubbles', 'Body Wash', 'Exfoliant & Scrub', 'Hair Removal', 'Hand & Foot Care', 'Hand Soap', 'Moisturizer & Body Oil', 'Suncare & Tanning', 'Tools', 'None']
        } else if (category === 'Women Other') {
            choices = ['None']
        } else if (category === 'Men Accessories') {
            choices = ['Belts', 'Cuff Links', 'Face Masks', 'Glasses', 'Gloves', 'Hats', 'Jewelry', 'Key & Card Holders', 'Money Clips', 'Phone Cases', 'Pocket Squares', 'Scarves', 'Sunglasses', 'Suspenders', 'Ties', 'Watches', 'None']
        } else if (category === 'Men Bags') {
            choices = ['Backpacks', 'Belt Bags', 'Briefcases', 'Duffel Bags', 'Laptop Bags', 'Luggage & Travel Bags', 'Messenger Bags', 'Toiletry Bags', 'Wallets', 'None']

        } else if (category === 'Men Jackets & Coats') {
            choices = ['Bomber & Varsity', 'Lightweight & Shirt Jackets', 'Military & Field', 'Pea Coats', 'Performance Jackets', 'Puffers', 'Raincoats', 'Ski & Snowboard', 'Trench Coats', 'Vests', 'Windbreakers', 'None']

        } else if (category === 'Men Jeans') {
            choices = ['Bootcut', 'Relaxed', 'Skinny', 'Slim', 'Slim Straight', 'Straight', 'None']

        } else if (category === 'Men Pants') {
            choices = ['Cargo', 'Chinos & Khakis', 'Corduroy', 'Dress', 'Sweatpants & Joggers', 'None']

        } else if (category === 'Men Shirts') {
            choices = ['Casual Button Down Shirts', 'Dress Shirts', 'Jerseys', 'Polos', 'Sweatshirts & Hoodies', 'Tank Tops', 'Tees - Long Sleeve', 'Tees - Short Sleeve', 'None']

        } else if (category === 'Men Shoes') {
            choices = ['Athletic Shoes', 'Boat Shoes', 'Boots', 'Chukka Boots', 'Cowboy & Western Boots', 'Loafers & Slip-Ons', 'Oxfords & Derbys', 'Rain & Snow Boots', 'Sandals & Flip-Flops', 'Sneakers', 'None']

        } else if (category === 'Men Shorts') {
            choices = ['Athletic', 'Cargo', 'Flat Front', 'Hybrids', 'Jean Shorts', 'None']

        } else if (category === 'Men Suits & Blazers') {
            choices = ['Sport Coats & Blazers', 'Suits', 'Tuxedos', 'Vests', 'None']

        } else if (category === 'Men Sweaters') {
            choices = ['Cardigan', 'Crewneck', 'Turtleneck', 'V-Neck', 'Zip Up', 'None']

        } else if (category === 'Men Swim') {
            choices = ['Board Shorts', 'Hybrids', 'Rash Guards', 'Swim Trunks', 'None']

        } else if (category === 'Men Underwear & Socks') {
            choices = ['Athletic Socks', 'Boxer Briefs', 'Boxers', 'Briefs', 'Casual Socks', 'Dress Socks', 'Undershirts', 'None']

        } else if (category === 'Men Grooming') {
            choices = ['Cleanser', 'Grooming Tools', 'Hair Care', 'Moisturizer', 'Shaving', 'Suncare', 'Treatments', 'None']

        } else if (category === 'Men Other') {
            choices = ['None']

        } else if (category === 'Kids Accessories') {
            choices = ['Bags', 'Belts', 'Bibs', 'Diaper Covers', 'Face Masks', 'Hair Accessories', 'Hats', 'Jewelry',
                'Mittens', 'Socks & Tights', 'Sunglasses', 'Suspenders', 'Ties', 'Underwear', 'Watches', 'None']

        } else if (category === 'Kids Bottoms') {
            choices = ['Casual', 'Formal', 'Jeans', 'Jumpsuits & Rompers', 'Leggings', 'Overalls', 'Shorts', 'Skirts',
                'Skorts', 'Sweatpants & Joggers', 'None']
        } else if (category === 'Kids Dresses') {
            choices = ['Casual', 'Formal', 'None']

        } else if (category === 'Kids Jackets & Coats') {
            choices = ['Blazers', 'Capes', 'Jean Jackets', 'Pea Coats', 'Puffers', 'Raincoats', 'Vests', 'None']

        } else if (category === 'Kids Matching Sets') {
            choices = ['None']

        } else if (category === 'Kids One Pieces') {
            choices = ['Bodysuits', 'Footies', 'None']

        } else if (category === 'Kids Pajamas') {
            choices = ['Nightgowns', 'Pajama Bottoms', 'Pajama Sets', 'Pajama Tops', 'Robes', 'Sleep Sacks', 'None']

        } else if (category === 'Kids Shirts & Tops') {
            choices = ['Blouses', 'Button Down Shirts', 'Camisoles', 'Jerseys', 'Polos', 'Sweaters',
                'Sweatshirts & Hoodies', 'Tank Tops',
                'Tees - Long Sleeve', 'Tees - Short Sleeve', 'None']

        } else if (category === 'Kids Shoes') {
            choices = ['Baby & Walker', 'Boots', 'Dress Shoes', 'Moccasins', 'Rain & Snow Boots',
                'Sandals & Flip Flops', 'Slippers', 'Sneakers', 'Water Shoes', 'None']

        } else if (category === 'Kids Swim') {
            choices = ['Bikinis', 'Coverups', 'One Piece', 'Rashguards', 'Swim Trunks', 'None']

        } else if (category === 'Kids Costumes') {
            choices = ['Dance', 'Halloween', 'Seasonal', 'Superhero', 'Theater', 'None']

        } else if (category === 'Kids Bath, Skin & Hair') {
            choices = ['Bath & Body', 'Hair Care', 'Moisturizer', 'Suncare', 'Tools', 'None']

        } else if (category === 'Kids Toys') {
            choices = ['Action Figures & Playsets', 'Building Sets & Blocks', 'Cars & Vehicles', 'Dolls & Accessories',
                'Learning Toys', 'Puzzles & Games', 'Stuffed Animals', 'Trading Cards', 'None']

        } else if (category === 'Kids Other') {
            choices = ['None']

        } else if (category === 'Home Accents') {
            choices = ['Accent Pillows', 'Baskets & Bins', 'Candles & Holders', 'Coffee Table Books', 'Curtains & Drapes', 'Decor', 'Door Mats',
                'Faux Florals', 'Furniture Covers', 'Lanterns', 'Picture Frames', 'Vases', 'None']

        } else if (category === 'Home Bath') {
            choices = ['Bath Accessories', 'Bath Storage', 'Bath Towels', 'Beach Towels', 'Hand Towels', 'Mats', 'Shower Curtains',
                'Vanity Mirrors', 'Vanity Trays', 'Wash Cloths', 'None']

        } else if (category === 'Home Bedding') {
            choices = ['Blankets & Throws', 'Comforters', 'Duvet Covers', 'Mattress Covers', 'Pillows', 'Quilts', 'Sheets', 'None']

        } else if (category === 'Home Dinning') {
            choices = ['Bar Accessories', 'Dinnerware',
                'Drinkware', 'Flatware', 'Mugs', 'Serveware', 'Serving Utensils', 'Table Linens',
                'Water Bottles & Thermoses', 'None']

        } else if (category === 'Home Games') {
            choices = ['Card Games', 'Outdoor Games', 'Puzzles', 'None']

        } else if (category === 'Home Holiday') {
            choices = ['Garland', 'Blouses', 'Button Down Shirts', 'Camisoles', 'Jerseys', 'Polos', 'Sweaters',
                'Sweatshirts & Hoodies', 'Tank Tops', 'Tees - Long Sleeve', 'Tees - Short Sleeve', 'None']

        } else if (category === 'Home Kitchen') {
            choices = ['BBQ & Grilling Tools', 'Bakeware', 'Coffee & Tea Accessories', 'Cookbooks', 'Cooking Utensils', 'Cookware', 'Food Storage',
                'Kitchen Linens', 'Kitchen Tools', 'Knives & Cutlery', 'None']

        } else if (category === 'Home Office') {
            choices = ['Arts & Crafts', 'Binders & Folders', 'Calendars', 'Labels & Label Makers', 'Notebooks & Journals', 'Pencil Cases',
                'Planners', 'Shipping Supplies', 'Stationery', 'None']

        } else if (category === 'Home Party Supplies') {
            choices = ['Cake Candles', 'Cake Toppers', 'Cards & Invitations', 'Decorations', 'Disposable Tableware', 'Favors', 'Gift Wrap',
                'Hats', 'Party Lights', 'None']

        } else if (category === 'Home Storage & Organization') {
            choices = ['Closet Accessories', 'Drawer Liners', 'Garment Bags', 'Jewelry Organizers', 'Makeup Organizers', 'Storage', 'None']

        } else if (category === 'Home Wall Art') {
            choices = ['Art & Decals', 'Clocks', 'Display Shelves', 'Hooks', 'Mirrors', 'Tapestries', 'Wallpaper', 'None']

        } else if (category === 'Home Other') {
            choices = ['None']
        } else if (category === 'Pets Dog') {
            choices = ['Bedding & Blankets', 'Bowls & Feeders', 'Carriers & Travel', 'Clothing & Accessories', 'Collars, Leashes & Harnesses',
                'Grooming', 'Housebreaking', 'Toys', 'None']

        } else if (category === 'Pets Cat') {
            choices = ['Beds', 'Bowls & Feeders', 'Carriers & Travel', 'Clothing & Accessories', 'Collars, Leashes  & Harnesses',
                'Grooming', 'Scratchers', 'Toys', 'None']

        } else if (category === 'Pets Bird') {
            choices = ['Cages & Covers', 'Feeders & Waterers', 'Perches & Swings', 'Toys', 'None']

        } else if (category === 'Pets Fish') {
            choices = ['Aquarium Kits', 'Cleaning & Maintenance', 'Decor & Accessories', 'None']

        } else if (category === 'Pets Reptile') {
            choices = ['Cleaning & Maintenance', 'Habitats', 'Habitat Accessories', 'Heating & Lights', 'None']

        } else if (category === 'Pets Small Pets') {
            choices = ['Bedding', 'Bowls & Feeders', 'Cages & Habitats', 'Carriers', 'Grooming', 'Habitat Accessories', 'Toys', 'None']

        } else if (category === 'Pets Other') {
            choices = ['None']
        }

        subcategory.empty();
        subcategory.append(`<option disabled selected>Select a Subcategory</option>`);
        $.each(choices, function(index, value) {

            subcategory.append(`<option value="${value}">${value}</option>`);
        });

    });
    $('#yes_button').click(function () {
        let no_button = $('#no_button');
        let yes_button = $('#yes_button');
        let tags = $('#id_tags');

        no_button.addClass('btn-outline-dark').removeClass('btn-dark');
        yes_button.addClass('btn-dark').removeClass('btn-outline-dark');

        tags.val('True')

    });
    $('#no_button').click(function () {
        let yes_button = $('#yes_button');
        let no_button = $('#no_button');
        let tags = $('#id_tags');

        yes_button.addClass('btn-outline-dark').removeClass('btn-dark');
        no_button.addClass('btn-dark').removeClass('btn-outline-dark');

        tags.val('False')

    });
    $("#id_original_price").inputFilter(function(value) {
        return /^\d*$/.test(value);    // Allow digits only, using a RegExp
    });
    $("#id_listing_price").inputFilter(function(value) {
        return /^\d*$/.test(value);    // Allow digits only, using a RegExp
    });
});
