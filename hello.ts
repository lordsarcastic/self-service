type JSX = {
    // defining so I don't have red in my editor
}

class FormBuilder {
    // defines all the code and stuff needed to build a form template
    build (): JSX {
        // creates JSX of the form
        return {}
    }
}

class MyFormBuilder extends FormBuilder {
    // user defines path to all templates they want to use throughout the app
    TextField = "x" // template for text field
    EmailField = "y" //template for email field
}


class CreateUserForm extends MyFormBuilder {
    name: TextField
    email: EmailField
}


const CreateUserReactComponent = () => {
    return (
        <>
            {CreateUserForm.build()}
        </>
    )
}